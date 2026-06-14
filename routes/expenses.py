from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from models import db, Group, GroupMember, Expense, ExpenseSplit, Comment, User
from decimal import Decimal, InvalidOperation

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/groups/<int:group_id>/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense(group_id):
    # Verify group membership
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to add expenses to this group.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    # Default currently active members for display
    active_members = GroupMember.query.filter_by(group_id=group_id, left_at=None).all()
    
    if request.method == 'POST':
        description = request.form.get('description')
        amount_str = request.form.get('total_amount') # This is the original entered amount
        paid_by_id = request.form.get('paid_by_id')
        split_type = request.form.get('split_type')
        date_str = request.form.get('date')
        currency = request.form.get('currency', 'INR').strip().upper()
        rate_str = request.form.get('exchange_rate', '1.0')
        
        # 1. Validation
        if not description or not amount_str or not paid_by_id or not split_type or not date_str:
            flash('All fields are required.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        try:
            date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date selected.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        try:
            original_amount = Decimal(amount_str)
            if original_amount <= 0:
                raise ValueError("Amount must be positive.")
        except (InvalidOperation, ValueError):
            flash('Please enter a valid positive amount.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        try:
            exchange_rate = Decimal(rate_str)
            if exchange_rate <= 0:
                raise ValueError("Exchange rate must be positive.")
        except (InvalidOperation, ValueError):
            flash('Please enter a valid positive exchange rate.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        try:
            paid_by_id = int(paid_by_id)
        except ValueError:
            flash('Invalid payer selected.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        # Verify paid_by_id is group member and was active on the date
        payer_mem = GroupMember.query.filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == paid_by_id,
            GroupMember.joined_at <= date_parsed,
            (GroupMember.left_at == None) | (GroupMember.left_at >= date_parsed)
        ).first()
        if not payer_mem:
            flash('Payer must be an active member of the group on the selected date.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        # Converted total amount in group base currency (INR)
        total_amount = (original_amount * exchange_rate).quantize(Decimal('0.01'))
            
        # 2. Parsing split inputs based on split_type
        participants_ids = []
        percentages = {}
        shares = {}
        
        # We also need to retrieve list of active members on that date for loop logic
        active_on_date = GroupMember.query.filter(
            GroupMember.group_id == group_id,
            GroupMember.joined_at <= date_parsed,
            (GroupMember.left_at == None) | (GroupMember.left_at >= date_parsed)
        ).all()
        active_on_date_ids = [m.user_id for m in active_on_date]
        
        if split_type == 'equal':
            participant_strs = request.form.getlist('participants')
            if not participant_strs:
                flash('Please select at least one participant to split with.', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            try:
                participants_ids = [int(p) for p in participant_strs]
            except ValueError:
                flash('Invalid participant selection.', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
                
        elif split_type == 'percentage':
            total_percentage = Decimal('0.00')
            for member in active_on_date:
                pct_str = request.form.get(f'percentage_{member.user_id}', '0')
                if pct_str:
                    try:
                        pct = Decimal(pct_str)
                        if pct > 0:
                            percentages[member.user_id] = pct
                            total_percentage += pct
                            participants_ids.append(member.user_id)
                    except (InvalidOperation, ValueError):
                        flash(f'Invalid percentage input for user {member.user.full_name}.', 'danger')
                        return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
            if not participants_ids:
                flash('Please select at least one participant and enter a percentage.', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
                
            # Validate total percentage: must be between 99.99% and 100.01%
            if not (Decimal('99.99') <= total_percentage <= Decimal('100.01')):
                flash(f'Total percentages must sum to 100% (currently: {total_percentage}%).', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
                
        elif split_type == 'share':
            total_shares = 0
            for member in active_on_date:
                share_str = request.form.get(f'share_{member.user_id}', '0')
                if share_str:
                    try:
                        sh = int(share_str)
                        if sh > 0:
                            shares[member.user_id] = sh
                            total_shares += sh
                            participants_ids.append(member.user_id)
                    except ValueError:
                        flash(f'Invalid share input for user {member.user.full_name}.', 'danger')
                        return render_template('expenses/add_expense.html', group=group, active_members=active_members)
                        
            if not participants_ids:
                flash('Please select at least one participant and enter shares.', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
                
            if total_shares <= 0:
                flash('Total shares must be greater than zero.', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
        else:
            flash('Invalid split type selected.', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
        # Verify all split users are active members of this group on the expense date
        for pid in participants_ids:
            if pid not in active_on_date_ids:
                u_err = User.query.get(pid)
                flash(f'{u_err.full_name} was not an active member on the selected date {date_str}.', 'danger')
                return render_template('expenses/add_expense.html', group=group, active_members=active_members)
                
        # 3. Calculation of Splits (based on converted amount in base currency)
        split_amounts = {}
        N = len(participants_ids)
        sum_computed = Decimal('0.00')
        
        if split_type == 'equal':
            base_share = (total_amount / Decimal(str(N))).quantize(Decimal('0.01'))
            for i, pid in enumerate(participants_ids):
                if i == N - 1:
                    split_amounts[pid] = total_amount - (base_share * Decimal(str(N - 1)))
                else:
                    split_amounts[pid] = base_share
                    
        elif split_type == 'percentage':
            for i, pid in enumerate(participants_ids):
                if i == N - 1:
                    split_amounts[pid] = total_amount - sum_computed
                else:
                    amt = (total_amount * percentages[pid] / Decimal('100.00')).quantize(Decimal('0.01'))
                    split_amounts[pid] = amt
                    sum_computed += amt
                    
        elif split_type == 'share':
            for i, pid in enumerate(participants_ids):
                if i == N - 1:
                    split_amounts[pid] = total_amount - sum_computed
                else:
                    amt = (total_amount * Decimal(str(shares[pid])) / Decimal(str(total_shares))).quantize(Decimal('0.01'))
                    split_amounts[pid] = amt
                    sum_computed += amt
                    
        # 4. Save to database in a transaction
        try:
            new_expense = Expense(
                group_id=group_id,
                paid_by_id=paid_by_id,
                created_by_id=current_user.id,
                description=description,
                total_amount=total_amount,
                original_amount=original_amount,
                currency=currency,
                exchange_rate=exchange_rate,
                date=date_parsed,
                split_type=split_type
            )
            db.session.add(new_expense)
            db.session.flush() # Populate new_expense.id
            
            for pid in participants_ids:
                new_split = ExpenseSplit(
                    expense_id=new_expense.id,
                    user_id=pid,
                    amount=split_amounts[pid],
                    percentage=percentages.get(pid) if split_type == 'percentage' else None,
                    share=shares.get(pid) if split_type == 'share' else None
                )
                db.session.add(new_split)
                
            db.session.commit()
            flash(f'Expense "{description}" of Rs. {total_amount:.2f} ({original_amount:.2f} {currency}) added successfully!', 'success')
            return redirect(url_for('groups.group_detail', group_id=group_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return render_template('expenses/add_expense.html', group=group, active_members=active_members)
            
    return render_template('expenses/add_expense.html', group=group, active_members=active_members)

@expenses_bp.route('/expenses/<int:expense_id>')
@login_required
def expense_detail(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    
    # Verify user is group member
    membership = GroupMember.query.filter_by(group_id=expense.group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to view this expense.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    return render_template('expenses/expense_detail.html', expense=expense)

@expenses_bp.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    group_id = expense.group_id
    
    # Only creator of the expense can delete it
    if expense.created_by_id != current_user.id:
        flash('Only the creator of this expense can delete it.', 'danger')
        return redirect(url_for('expenses.expense_detail', expense_id=expense_id))
        
    try:
        # Cascade delete is handled by SQLAlchemy cascade configuration,
        # but we delete explicitly or trust CASCADE. Our schema definitions use ondelete='CASCADE'.
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting: {str(e)}', 'danger')
        
    return redirect(url_for('groups.group_detail', group_id=group_id))
