from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    memberships = db.relationship('GroupMember', back_populates='user', cascade='all, delete-orphan')
    comments = db.relationship('Comment', back_populates='user', cascade='all, delete-orphan')
    
    # We use primaryjoin for disambiguating multiple FKs to User in Expense and Settlement tables
    paid_expenses = db.relationship('Expense', foreign_keys='Expense.paid_by_id', back_populates='paid_by', cascade='all, delete-orphan')
    created_expenses = db.relationship('Expense', foreign_keys='Expense.created_by_id', back_populates='created_by', cascade='all, delete-orphan')
    
    sent_settlements = db.relationship('Settlement', foreign_keys='Settlement.payer_id', back_populates='payer', cascade='all, delete-orphan')
    received_settlements = db.relationship('Settlement', foreign_keys='Settlement.receiver_id', back_populates='receiver', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User {self.email}>"


class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    creator = db.relationship('User', foreign_keys=[creator_id])
    members = db.relationship('GroupMember', back_populates='group', cascade='all, delete-orphan')
    expenses = db.relationship('Expense', back_populates='group', cascade='all, delete-orphan')
    settlements = db.relationship('Settlement', back_populates='group', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Group {self.name}>"


class GroupMember(db.Model):
    __tablename__ = 'group_members'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    joined_at = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    left_at = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    group = db.relationship('Group', back_populates='members')
    user = db.relationship('User', back_populates='memberships')

    def __repr__(self):
        return f"<GroupMember Group:{self.group_id} User:{self.user_id}>"


class Expense(db.Model):
    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    paid_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    original_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='INR')
    exchange_rate = db.Column(db.Numeric(10, 6), nullable=False, default=1.0)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    split_type = db.Column(db.String(20), nullable=False) # 'equal', 'percentage', 'share', 'exact'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    group = db.relationship('Group', back_populates='expenses')
    paid_by = db.relationship('User', foreign_keys=[paid_by_id], back_populates='paid_expenses')
    created_by = db.relationship('User', foreign_keys=[created_by_id], back_populates='created_expenses')
    splits = db.relationship('ExpenseSplit', back_populates='expense', cascade='all, delete-orphan')
    comments = db.relationship('Comment', back_populates='expense', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Expense {self.description} Amount:{self.total_amount}>"


class ExpenseSplit(db.Model):
    __tablename__ = 'expense_splits'

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    percentage = db.Column(db.Numeric(5, 2), nullable=True)
    share = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    expense = db.relationship('Expense', back_populates='splits')
    user = db.relationship('User')

    def __repr__(self):
        return f"<ExpenseSplit Expense:{self.expense_id} User:{self.user_id} Amount:{self.amount}>"


class Settlement(db.Model):
    __tablename__ = 'settlements'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    payer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    original_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='INR')
    exchange_rate = db.Column(db.Numeric(10, 6), nullable=False, default=1.0)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    group = db.relationship('Group', back_populates='settlements')
    payer = db.relationship('User', foreign_keys=[payer_id], back_populates='sent_settlements')
    receiver = db.relationship('User', foreign_keys=[receiver_id], back_populates='received_settlements')

    def __repr__(self):
        return f"<Settlement Group:{self.group_id} {self.payer_id} -> {self.receiver_id} Amount:{self.amount}>"


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    expense = db.relationship('Expense', back_populates='comments')
    user = db.relationship('User', back_populates='comments')

    def __repr__(self):
        return f"<Comment Expense:{self.expense_id} User:{self.user_id}>"

class ExchangeRate(db.Model):
    __tablename__ = 'exchange_rates'

    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(3), nullable=False)
    to_currency = db.Column(db.String(3), nullable=False)
    rate = db.Column(db.Numeric(10, 6), nullable=False)
    date = db.Column(db.Date, nullable=True) # None means fallback rate

    def __repr__(self):
        return f"<ExchangeRate {self.from_currency} -> {self.to_currency}: {self.rate}>"
