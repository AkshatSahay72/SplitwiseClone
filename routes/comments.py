from flask import Blueprint, redirect, url_for, flash, request
from flask_login import current_user, login_required
from models import db, Expense, GroupMember, Comment

comments_bp = Blueprint('comments', __name__)

@comments_bp.route('/expenses/<int:expense_id>/comments', methods=['POST'])
@login_required
def add_comment(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    
    # Verify user is group member
    membership = GroupMember.query.filter_by(group_id=expense.group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to comment on this expense.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    content = request.form.get('content')
    if not content or not content.strip():
        flash('Comment content cannot be empty.', 'danger')
        return redirect(url_for('expenses.expense_detail', expense_id=expense_id))
        
    try:
        new_comment = Comment(
            expense_id=expense_id,
            user_id=current_user.id,
            content=content.strip()
        )
        db.session.add(new_comment)
        db.session.commit()
        flash('Comment posted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        
    return redirect(url_for('expenses.expense_detail', expense_id=expense_id))
