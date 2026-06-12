import unittest
from decimal import Decimal
from app import create_app
from models import db, User, Group, GroupMember, Expense, ExpenseSplit, Settlement
from routes.groups import get_group_balances, simplify_debts

class SplitwiseAlgorithmsTestCase(unittest.TestCase):
    def setUp(self):
        # Create Flask app configured for testing with in-memory SQLite
        self.app = create_app({
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'TESTING': True,
            'WTF_CSRF_ENABLED': False
        })
        
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create all tables in memory
        db.create_all()
        
        # Create test users
        self.user_a = User(full_name="User A", email="a@test.com", password="password")
        self.user_b = User(full_name="User B", email="b@test.com", password="password")
        self.user_c = User(full_name="User C", email="c@test.com", password="password")
        db.session.add_all([self.user_a, self.user_b, self.user_c])
        db.session.commit()
        
        # Create a test group
        self.group = Group(name="Trip Group", creator_id=self.user_a.id)
        db.session.add(self.group)
        db.session.commit()
        
        # Add members to the group
        self.member_a = GroupMember(group_id=self.group.id, user_id=self.user_a.id)
        self.member_b = GroupMember(group_id=self.group.id, user_id=self.user_b.id)
        self.member_c = GroupMember(group_id=self.group.id, user_id=self.user_c.id)
        db.session.add_all([self.member_a, self.member_b, self.member_c])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_equal_split_rounding(self):
        """
        Verify that splitting Rs. 100.00 equally among 3 users results in:
        User A: 33.33
        User B: 33.33
        User C: 33.34
        And they sum to exactly 100.00.
        """
        total_amount = Decimal('100.00')
        participants = [self.user_a.id, self.user_b.id, self.user_c.id]
        N = len(participants)
        
        # Emulate the route split math
        base_share = (total_amount / Decimal(str(N))).quantize(Decimal('0.01'))
        split_amounts = {}
        for i, pid in enumerate(participants):
            if i == N - 1:
                split_amounts[pid] = total_amount - (base_share * Decimal(str(N - 1)))
            else:
                split_amounts[pid] = base_share
                
        self.assertEqual(split_amounts[self.user_a.id], Decimal('33.33'))
        self.assertEqual(split_amounts[self.user_b.id], Decimal('33.33'))
        self.assertEqual(split_amounts[self.user_c.id], Decimal('33.34'))
        self.assertEqual(sum(split_amounts.values()), total_amount)

    def test_percentage_split_rounding(self):
        """
        Verify percentage split of Rs. 100.00 with 33.33%, 33.33%, 33.33% (sum = 99.99%)
        which is within tolerance.
        """
        total_amount = Decimal('100.00')
        participants = [self.user_a.id, self.user_b.id, self.user_c.id]
        percentages = {
            self.user_a.id: Decimal('33.33'),
            self.user_b.id: Decimal('33.33'),
            self.user_c.id: Decimal('33.33')
        }
        N = len(participants)
        
        # Emulate route split math
        split_amounts = {}
        sum_computed = Decimal('0.00')
        for i, pid in enumerate(participants):
            if i == N - 1:
                split_amounts[pid] = total_amount - sum_computed
            else:
                amt = (total_amount * percentages[pid] / Decimal('100.00')).quantize(Decimal('0.01'))
                split_amounts[pid] = amt
                sum_computed += amt
                
        self.assertEqual(split_amounts[self.user_a.id], Decimal('33.33'))
        self.assertEqual(split_amounts[self.user_b.id], Decimal('33.33'))
        self.assertEqual(split_amounts[self.user_c.id], Decimal('33.34'))
        self.assertEqual(sum(split_amounts.values()), total_amount)

    def test_share_split_rounding(self):
        """
        Verify share split of Rs. 100.00 with 1, 1, 1 shares (total shares = 3)
        """
        total_amount = Decimal('100.00')
        participants = [self.user_a.id, self.user_b.id, self.user_c.id]
        shares = {
            self.user_a.id: 1,
            self.user_b.id: 1,
            self.user_c.id: 1
        }
        total_shares = 3
        N = len(participants)
        
        # Emulate route split math
        split_amounts = {}
        sum_computed = Decimal('0.00')
        for i, pid in enumerate(participants):
            if i == N - 1:
                split_amounts[pid] = total_amount - sum_computed
            else:
                amt = (total_amount * Decimal(str(shares[pid])) / Decimal(str(total_shares))).quantize(Decimal('0.01'))
                split_amounts[pid] = amt
                sum_computed += amt
                
        self.assertEqual(split_amounts[self.user_a.id], Decimal('33.33'))
        self.assertEqual(split_amounts[self.user_b.id], Decimal('33.33'))
        self.assertEqual(split_amounts[self.user_c.id], Decimal('33.34'))
        self.assertEqual(sum(split_amounts.values()), total_amount)

    def test_debt_simplification_and_balances(self):
        """
        Create a scenario:
        User A paid Rs. 90.00 for Cab split equally A, B, C (A gets +60, B gets -30, C gets -30)
        Then User B logs a payment/settlement to User A of Rs. 30.00 (A is owed +30, B is 0, C is -30)
        Then verify balances and simplify_debts output:
        Should show: User C owes User A Rs. 30.00
        """
        # Add expense of 90 paid by A
        expense = Expense(
            group_id=self.group.id,
            paid_by_id=self.user_a.id,
            created_by_id=self.user_a.id,
            description="Taxi fare",
            total_amount=Decimal('90.00'),
            split_type="equal"
        )
        db.session.add(expense)
        db.session.flush()
        
        # Add splits of 30 each
        split_a = ExpenseSplit(expense_id=expense.id, user_id=self.user_a.id, amount=Decimal('30.00'))
        split_b = ExpenseSplit(expense_id=expense.id, user_id=self.user_b.id, amount=Decimal('30.00'))
        split_c = ExpenseSplit(expense_id=expense.id, user_id=self.user_c.id, amount=Decimal('30.00'))
        db.session.add_all([split_a, split_b, split_c])
        db.session.commit()
        
        # Get balances
        balances = get_group_balances(self.group)
        self.assertEqual(balances[self.user_a.id], Decimal('60.00'))
        self.assertEqual(balances[self.user_b.id], Decimal('-30.00'))
        self.assertEqual(balances[self.user_c.id], Decimal('-30.00'))
        
        # Log settlement B pays A Rs. 30.00
        settlement = Settlement(
            group_id=self.group.id,
            payer_id=self.user_b.id,
            receiver_id=self.user_a.id,
            amount=Decimal('30.00')
        )
        db.session.add(settlement)
        db.session.commit()
        
        # Recalculate balances after settlement
        balances = get_group_balances(self.group)
        self.assertEqual(balances[self.user_a.id], Decimal('30.00'))
        self.assertEqual(balances[self.user_b.id], Decimal('0.00'))
        self.assertEqual(balances[self.user_c.id], Decimal('-30.00'))
        
        # Simplify debts
        user_map = {
            self.user_a.id: self.user_a,
            self.user_b.id: self.user_b,
            self.user_c.id: self.user_c
        }
        txs = simplify_debts(balances, user_map)
        
        # Should be: C owes A 30.00
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]['from_user'].id, self.user_c.id)
        self.assertEqual(txs[0]['to_user'].id, self.user_a.id)
        self.assertEqual(txs[0]['amount'], Decimal('30.00'))

if __name__ == '__main__':
    unittest.main()
