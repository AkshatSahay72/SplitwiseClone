from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from models import db, Group, GroupMember, Settlement
from decimal import Decimal, InvalidOperation
from datetime import datetime

settlements_bp = Blueprint('settlements', __name__)

@settlements_bp.route('/groups/<int:group_id>/settle', methods=['GET', 'POST'])
@login_required
def create_settlement(group_id):
    # Verify group membership
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to log settlements for this group.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    # Default currently active members for display
    active_members = GroupMember.query.filter_by(group_id=group_id, left_at=None).all()
    
    if request.method == 'POST':
        payer_id_str = request.form.get('payer_id')
        receiver_id_str = request.form.get('receiver_id')
        amount_str = request.form.get('amount')
        date_str = request.form.get('date')
        currency = request.form.get('currency', 'INR').strip().upper()
        rate_str = request.form.get('exchange_rate', '1.0')
        
        if not payer_id_str or not receiver_id_str or not amount_str or not date_str:
            flash('All fields are required.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        try:
            date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date selected.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        try:
            payer_id = int(payer_id_str)
            receiver_id = int(receiver_id_str)
        except ValueError:
            flash('Invalid member selection.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        try:
            original_amount = Decimal(amount_str)
            if original_amount <= 0:
                raise ValueError("Amount must be positive.")
        except (InvalidOperation, ValueError):
            flash('Please enter a valid positive amount.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        try:
            exchange_rate = Decimal(rate_str)
            if exchange_rate <= 0:
                raise ValueError("Exchange rate must be positive.")
        except (InvalidOperation, ValueError):
            flash('Please enter a valid positive exchange rate.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        if payer_id == receiver_id:
            flash('Payer and receiver cannot be the same person.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        # Verify both are members of the group and were active on that date
        payer_mem = GroupMember.query.filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == payer_id,
            GroupMember.joined_at <= date_parsed,
            (GroupMember.left_at == None) | (GroupMember.left_at >= date_parsed)
        ).first()
        
        receiver_mem = GroupMember.query.filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == receiver_id,
            GroupMember.joined_at <= date_parsed,
            (GroupMember.left_at == None) | (GroupMember.left_at >= date_parsed)
        ).first()
        
        if not payer_mem or not receiver_mem:
            flash('Both payer and receiver must be active members of the group on the selected date.', 'danger')
            return render_template('settlements/settle.html', group=group, active_members=active_members)
            
        amount = (original_amount * exchange_rate).quantize(Decimal('0.01'))
            
        try:
            new_settlement = Settlement(
                group_id=group_id,
                payer_id=payer_id,
                receiver_id=receiver_id,
                amount=amount,
                original_amount=original_amount,
                currency=currency,
                exchange_rate=exchange_rate,
                date=date_parsed
            )
            db.session.add(new_settlement)
            db.session.commit()
            
            # Fetch user names for feedback
            from models import User
            payer_user = User.query.get(payer_id)
            receiver_user = User.query.get(receiver_id)
            
            flash(f'Settlement recorded: {payer_user.full_name} paid {receiver_user.full_name} Rs. {amount:.2f} ({original_amount:.2f} {currency})', 'success')
            return redirect(url_for('groups.group_detail', group_id=group_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            
    return render_template('settlements/settle.html', group=group, active_members=active_members)

