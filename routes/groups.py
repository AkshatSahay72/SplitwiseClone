from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from models import db, User, Group, GroupMember, Expense, Settlement, ExpenseSplit
from decimal import Decimal

groups_bp = Blueprint('groups', __name__)

def get_group_balances(group):
    """
    Calculates the net balances of all members in a group
    and computes the simplified debt transactions to show who owes whom.
    """
    # 1. Initialize balances for all group members to 0.00
    balances = {member.user_id: Decimal('0.00') for member in group.members}
    
    # 2. Add total paid by each user and subtract their splits
    for expense in group.expenses:
        # Add to the payer's balance
        if expense.paid_by_id in balances:
            balances[expense.paid_by_id] += Decimal(str(expense.total_amount))
        
        # Subtract splits from each user's balance
        for split in expense.splits:
            if split.user_id in balances:
                balances[split.user_id] -= Decimal(str(split.amount))
                
    # 3. Add sent settlements (payer gets credited) and subtract received settlements (receiver gets debited)
    for settlement in group.settlements:
        if settlement.payer_id in balances:
            balances[settlement.payer_id] += Decimal(str(settlement.amount))
        if settlement.receiver_id in balances:
            balances[settlement.receiver_id] -= Decimal(str(settlement.amount))
            
    return balances

def simplify_debts(balances, user_map):
    """
    Greedy debt simplification algorithm.
    Takes a dict of {user_id: net_balance} and a user name map {user_id: User object}.
    Returns a list of dicts: [{'from_user': User, 'to_user': User, 'amount': Decimal}]
    """
    # Create debtor and creditor lists
    # Debtor has balance < 0 (owes money). We track debt as positive amount.
    debtors = []
    # Creditor has balance > 0 (is owed money).
    creditors = []
    
    for uid, bal in balances.items():
        if bal < -Decimal('0.009'):
            debtors.append({'user_id': uid, 'amount': -bal})
        elif bal > Decimal('0.009'):
            creditors.append({'user_id': uid, 'amount': bal})
            
    transactions = []
    
    # Greedily match
    while debtors and creditors:
        # Sort debtors descending by amount (largest debt first)
        debtors.sort(key=lambda x: x['amount'], reverse=True)
        # Sort creditors descending by amount (largest credit first)
        creditors.sort(key=lambda x: x['amount'], reverse=True)
        
        debtor = debtors[0]
        creditor = creditors[0]
        
        settle_amount = min(debtor['amount'], creditor['amount'])
        
        # Avoid zero or micro transactions
        if settle_amount > Decimal('0.009'):
            transactions.append({
                'from_user': user_map.get(debtor['user_id']),
                'to_user': user_map.get(creditor['user_id']),
                'amount': settle_amount.quantize(Decimal('0.01'))
            })
            
        debtor['amount'] -= settle_amount
        creditor['amount'] -= settle_amount
        
        # Remove completed balances
        if debtor['amount'] < Decimal('0.009'):
            debtors.pop(0)
        if creditor['amount'] < Decimal('0.009'):
            creditors.pop(0)
            
    return transactions

@groups_bp.route('/dashboard')
@login_required
def dashboard():
    # Fetch all groups current user is a member of
    user_memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in user_memberships]
    
    user_groups = []
    total_owed = Decimal('0.00')
    total_owe = Decimal('0.00')
    
    for gid in group_ids:
        group = Group.query.get(gid)
        if not group:
            continue
        
        balances = get_group_balances(group)
        user_bal = balances.get(current_user.id, Decimal('0.00'))
        
        if user_bal > 0:
            total_owed += user_bal
        elif user_bal < 0:
            total_owe += -user_bal
            
        user_groups.append({
            'group': group,
            'balance': user_bal
        })
        
    # Get recent expenses across all user's groups
    recent_expenses = []
    if group_ids:
        recent_expenses = Expense.query.filter(Expense.group_id.in_(group_ids))\
            .order_by(Expense.created_at.desc()).limit(10).all()
            
    net_balance = total_owed - total_owe

    return render_template(
        'dashboard.html',
        user_groups=user_groups,
        total_owed=total_owed,
        total_owe=total_owe,
        net_balance=net_balance,
        recent_expenses=recent_expenses
    )

@groups_bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Group name is required.', 'danger')
            return render_template('groups/create.html')
            
        new_group = Group(
            name=name,
            description=description,
            creator_id=current_user.id
        )
        db.session.add(new_group)
        db.session.flush() # Flushes to database to populate new_group.id
        
        # Auto-join creator as member
        membership = GroupMember(
            group_id=new_group.id,
            user_id=current_user.id
        )
        db.session.add(membership)
        db.session.commit()
        
        flash(f'Group "{name}" created successfully!', 'success')
        return redirect(url_for('groups.group_detail', group_id=new_group.id))
        
    return render_template('groups/create.html')

@groups_bp.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    # Verify current user is a member of this group
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to view this group.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    
    # Calculate group balances
    balances = get_group_balances(group)
    
    # Get user details for name mapping
    member_user_ids = [m.user_id for m in group.members]
    users_list = User.query.filter(User.id.in_(member_user_ids)).all()
    user_map = {u.id: u for u in users_list}
    
    # Simplify debts
    simplified_debts = simplify_debts(balances, user_map)
    
    # Prepare member list with balance details (aggregating multiple intervals if a member rejoined)
    members_data = []
    seen_users = set()
    for m in group.members:
        if m.user_id in seen_users:
            continue
        seen_users.add(m.user_id)
        user_info = user_map.get(m.user_id)
        if user_info:
            # Query all intervals
            intervals = GroupMember.query.filter_by(group_id=group_id, user_id=m.user_id).all()
            is_active = any(um.left_at is None for um in intervals)
            formatted_intervals = []
            for um in intervals:
                joined_str = um.joined_at.strftime('%b %d, %Y')
                left_str = um.left_at.strftime('%b %d, %Y') if um.left_at else 'Present'
                formatted_intervals.append(f"{joined_str} to {left_str}")
                
            members_data.append({
                'user': user_info,
                'balance': balances.get(m.user_id, Decimal('0.00')),
                'is_active': is_active,
                'intervals': formatted_intervals
            })
            
    # All registered users for the "Add Member" dropdown (except currently active in group)
    active_member_ids = [m.user_id for m in group.members if m.left_at is None]
    all_registered_users = User.query.filter(~User.id.in_(active_member_ids)).order_by(User.full_name).all()

    # Expenses in this group (latest first)
    expenses = Expense.query.filter_by(group_id=group_id).order_by(Expense.date.desc(), Expense.created_at.desc()).all()
    
    # Settlements in this group (latest first)
    settlements = Settlement.query.filter_by(group_id=group_id).order_by(Settlement.date.desc(), Settlement.created_at.desc()).all()

    # Current user's net balance in this group
    current_user_balance = balances.get(current_user.id, Decimal('0.00'))

    return render_template(
        'groups/detail.html',
        group=group,
        members_data=members_data,
        expenses=expenses,
        settlements=settlements,
        simplified_debts=simplified_debts,
        all_registered_users=all_registered_users,
        current_user_balance=current_user_balance
    )

@groups_bp.route('/groups/<int:group_id>/add-member', methods=['POST'])
@login_required
def add_member(group_id):
    # Verify current user is member
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    user_id_to_add = request.form.get('user_id')
    if not user_id_to_add:
        flash('Please select a user to add.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    user_to_add = User.query.get(user_id_to_add)
    if not user_to_add:
        flash('Selected user does not exist.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    # Check if already has an active membership
    existing_active = GroupMember.query.filter_by(group_id=group_id, user_id=user_to_add.id, left_at=None).first()
    if existing_active:
        flash('User is already an active member of this group.', 'warning')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    from datetime import datetime, timezone
    new_member = GroupMember(
        group_id=group_id, 
        user_id=user_to_add.id,
        joined_at=datetime.now(timezone.utc).date()
    )
    db.session.add(new_member)
    db.session.commit()
    
    flash(f'{user_to_add.full_name} has been added to the group.', 'success')
    return redirect(url_for('groups.group_detail', group_id=group_id))

@groups_bp.route('/groups/<int:group_id>/remove-member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    
    # Only the creator of the group can remove members
    if group.creator_id != current_user.id:
        flash('Only the group creator can remove members.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    # Creator cannot remove themselves unless they transfer ownership
    if user_id == current_user.id:
        flash('You cannot remove yourself from the group. You must transfer group ownership first.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id, left_at=None).first()
    if not member:
        flash('User is not an active member of this group.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    from datetime import datetime, timezone
    member.left_at = datetime.now(timezone.utc).date()
    db.session.commit()
    
    flash('Member removed successfully.', 'success')
    return redirect(url_for('groups.group_detail', group_id=group_id))

@groups_bp.route('/groups/<int:group_id>/members/<int:user_id>/ledger')
@login_required
def member_ledger(group_id, user_id):
    # Verify current user is member of the group
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    target_user = User.query.get_or_404(user_id)
    
    # 1. Fetch all transactions involving target_user in this group
    # A. Expenses paid by target_user
    paid_expenses = Expense.query.filter_by(group_id=group_id, paid_by_id=user_id).all()
    # B. Splits owed by target_user
    owed_splits = ExpenseSplit.query.join(Expense).filter(Expense.group_id == group_id, ExpenseSplit.user_id == user_id).all()
    # C. Settlements sent by target_user (payer)
    sent_settlements = Settlement.query.filter_by(group_id=group_id, payer_id=user_id).all()
    # D. Settlements received by target_user (receiver)
    received_settlements = Settlement.query.filter_by(group_id=group_id, receiver_id=user_id).all()
    
    # 2. Combine into ledger items list
    ledger_items = []
    
    for exp in paid_expenses:
        ledger_items.append({
            'date': exp.date,
            'created_at': exp.created_at,
            'desc': exp.description,
            'type': 'Expense Paid',
            'orig_amount': exp.original_amount,
            'currency': exp.currency,
            'rate': exp.exchange_rate,
            'amount_inr': exp.total_amount,
            'impact': exp.total_amount, # Positive impact
            'ref_id': exp.id,
            'ref_type': 'expense'
        })
        
    for split in owed_splits:
        exp = split.expense
        ledger_items.append({
            'date': exp.date,
            'created_at': exp.created_at,
            'desc': f"Share of: {exp.description}",
            'type': 'Expense Shared/Owed',
            'orig_amount': (split.amount / exp.exchange_rate).quantize(Decimal('0.01')) if exp.exchange_rate else split.amount,
            'currency': exp.currency,
            'rate': exp.exchange_rate,
            'amount_inr': split.amount,
            'impact': -split.amount, # Negative impact
            'ref_id': exp.id,
            'ref_type': 'expense'
        })
        
    for stl in sent_settlements:
        ledger_items.append({
            'date': stl.date,
            'created_at': stl.created_at,
            'desc': f"Settlement paid to {stl.receiver.full_name}",
            'type': 'Settlement Sent',
            'orig_amount': stl.original_amount,
            'currency': stl.currency,
            'rate': stl.exchange_rate,
            'amount_inr': stl.amount,
            'impact': stl.amount, # Positive impact
            'ref_id': stl.id,
            'ref_type': 'settlement'
        })
        
    for stl in received_settlements:
        ledger_items.append({
            'date': stl.date,
            'created_at': stl.created_at,
            'desc': f"Settlement received from {stl.payer.full_name}",
            'type': 'Settlement Received',
            'orig_amount': stl.original_amount,
            'currency': stl.currency,
            'rate': stl.exchange_rate,
            'amount_inr': stl.amount,
            'impact': -stl.amount, # Negative impact
            'ref_id': stl.id,
            'ref_type': 'settlement'
        })
        
    # 3. Sort chronologically by date, and fall back to created_at
    ledger_items.sort(key=lambda x: (x['date'], x['created_at']))
    
    # 4. Calculate running balance
    running = Decimal('0.00')
    for item in ledger_items:
        running += item['impact']
        item['running_balance'] = running
        
    return render_template(
        'groups/ledger.html',
        group=group,
        target_user=target_user,
        ledger_items=ledger_items,
        total_balance=running
    )
