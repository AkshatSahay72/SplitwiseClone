import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import current_user, login_required
from models import db, User, Group, GroupMember, Expense, ExpenseSplit, Settlement, ExchangeRate
from routes.groups import get_group_balances

importer_bp = Blueprint('importer', __name__)

def parse_csv_date(date_str):
    """
    Parses date strings with various common formats.
    Returns (date_obj, warning_message).
    """
    date_str = date_str.strip()
    # Standard format DD-MM-YYYY
    for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt).date(), None
        except ValueError:
            continue
            
    # Handle month abbreviations (e.g., Mar-14) or similar
    for fmt in ('%b-%d', '%d-%b', '%b/%d', '%d/%b'):
        try:
            dt = datetime.strptime(date_str, fmt)
            # Default to year 2026 based on the project's data context
            return dt.replace(year=2026).date(), "Year defaulted to 2026"
        except ValueError:
            continue
            
    # Try fallback formats
    try:
        from dateutil import parser
        return parser.parse(date_str).date(), "Parsed via fuzzy dateutil"
    except Exception:
        pass
        
    return None, "Invalid date format"

@importer_bp.route('/groups/<int:group_id>/import', methods=['GET'])
@login_required
def import_csv_view(group_id):
    # Verify group membership
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to import to this group.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    return render_template('groups/import.html', group=group)

@importer_bp.route('/groups/<int:group_id>/import/analyze', methods=['POST'])
@login_required
def analyze_csv(group_id):
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    
    file = request.files.get('csv_file')
    if not file or file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('importer.import_csv_view', group_id=group_id))
        
    if not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'danger')
        return redirect(url_for('importer.import_csv_view', group_id=group_id))
        
    # Read the CSV content
    try:
        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        flash(f'Error reading CSV: {e}', 'danger')
        return redirect(url_for('importer.import_csv_view', group_id=group_id))
        
    # Query current group members and database users for resolver
    registered_users = User.query.all()
    user_by_name = {u.full_name.lower().strip(): u for u in registered_users}
    user_by_email = {u.email.lower().strip(): u for u in registered_users}
    
    # Query existing expenses to check for duplicates
    existing_expenses = Expense.query.filter_by(group_id=group_id).all()
    existing_keys = set()
    for e in existing_expenses:
        # Key: (description, date, amount)
        existing_keys.add((e.description.lower().strip(), e.date, e.total_amount))
        
    # Process rows
    parsed_rows = []
    unique_names_in_csv = set()
    csv_keys_seen = set()
    
    # Default exchange rates
    rates = {
        ('USD', 'INR'): Decimal('83.00'),
        ('INR', 'USD'): Decimal('0.012'),
        ('INR', 'INR'): Decimal('1.00'),
        ('USD', 'USD'): Decimal('1.00')
    }
    # Load dynamic rates
    db_rates = ExchangeRate.query.all()
    for r in db_rates:
        rates[(r.from_currency, r.to_currency)] = Decimal(str(r.rate))

    for idx, row in enumerate(reader, start=2): # Start at 2 for row reference
        date_str = row.get('date', '')
        desc = row.get('description', '')
        paid_by = row.get('paid_by', '')
        amount_str = row.get('amount', '0')
        curr = row.get('currency', '').strip().upper()
        split_type = row.get('split_type', '').strip().lower()
        split_with_str = row.get('split_with', '')
        split_details = row.get('split_details', '')
        notes = row.get('notes', '')
        
        anomalies = []
        action_taken = "Will import as Expense"
        
        # 1. Parse Date
        date_obj, date_warn = parse_csv_date(date_str)
        if not date_obj:
            anomalies.append({'type': 'error', 'message': f"Date parsing failed: {date_warn}"})
        elif date_warn:
            anomalies.append({'type': 'warning', 'message': f"Date resolved: {date_warn} ({date_obj})"})
            
        # 2. Parse Amount
        try:
            # Handle comma in strings (e.g., "1,200")
            cleaned_amount_str = amount_str.replace(',', '').strip()
            amount = Decimal(cleaned_amount_str)
            if amount == 0:
                anomalies.append({'type': 'warning', 'message': "Amount is zero. Will be skipped."})
                action_taken = "Will skip"
        except (InvalidOperation, ValueError):
            amount = Decimal('0.00')
            anomalies.append({'type': 'error', 'message': f"Invalid amount representation: '{amount_str}'"})
            action_taken = "Will skip"
            
        # 3. Currency Conversion
        if not curr:
            curr = 'INR'
            anomalies.append({'type': 'info', 'message': "Currency missing. Defaulted to INR."})
            
        rate = rates.get((curr, 'INR'), Decimal('1.00'))
        converted_amount = (amount * rate).quantize(Decimal('0.01'))
        if curr != 'INR':
            anomalies.append({'type': 'info', 'message': f"Converted {amount} {curr} to INR using rate {rate:.2f}."})
            
        # 4. Extract Names
        if paid_by and paid_by.strip():
            unique_names_in_csv.add(paid_by.strip())
        else:
            anomalies.append({'type': 'error', 'message': "Payer field is empty."})
            action_taken = "Will skip"
            
        split_with_names = []
        if split_with_str:
            split_with_names = [n.strip() for n in split_with_str.split(';') if n.strip()]
            for name in split_with_names:
                unique_names_in_csv.add(name)
                
        # 5. Check duplicate check
        if date_obj and desc:
            desc_key = desc.lower().strip()
            # Database check
            if (desc_key, date_obj, converted_amount) in existing_keys:
                anomalies.append({'type': 'warning', 'message': "Suspected duplicate: identical description, date, and amount exists in group."})
                action_taken = "Flagged as duplicate (User can ignore or override)"
            # Same CSV check
            csv_key = (desc_key, date_obj, converted_amount)
            if csv_key in csv_keys_seen:
                anomalies.append({'type': 'warning', 'message': "Suspected duplicate within the CSV file."})
                action_taken = "Flagged as duplicate (User can ignore or override)"
            csv_keys_seen.add(csv_key)

        # 6. Check Settlement vs Expense
        is_settlement = False
        if not split_type and len(split_with_names) == 1 and ("paid" in desc.lower() or "settle" in desc.lower() or "returned" in desc.lower() or "back" in desc.lower()):
            is_settlement = True
            action_taken = "Will import as Settlement"
            anomalies.append({'type': 'info', 'message': "Identified as a settlement transaction."})
            
        # 7. Split Math Check
        if not is_settlement and amount > 0:
            if split_type == 'percentage':
                # Parse split details percentages
                pcts = {}
                total_pct = Decimal('0.00')
                if split_details:
                    # e.g., Aisha 30%; Rohan 30%; Priya 30%; Meera 20%
                    parts = [p.strip() for p in split_details.split(';') if p.strip()]
                    for part in parts:
                        try:
                            # Split by space
                            subparts = part.rsplit(' ', 1)
                            if len(subparts) == 2:
                                name_key, val_str = subparts
                                val = Decimal(val_str.replace('%', '').strip())
                                pcts[name_key.strip()] = val
                                total_pct += val
                        except Exception:
                            pass
                if not (Decimal('99.99') <= total_pct <= Decimal('100.01')):
                    anomalies.append({'type': 'warning', 'message': f"Percentage splits total is {total_pct}% instead of 100%."})
                    
            elif split_type == 'share':
                # Parse split details shares
                shares = {}
                total_shares = 0
                if split_details:
                    # e.g., Aisha 1; Rohan 2; Priya 1; Dev 2
                    parts = [p.strip() for p in split_details.split(';') if p.strip()]
                    for part in parts:
                        try:
                            subparts = part.rsplit(' ', 1)
                            if len(subparts) == 2:
                                name_key, val_str = subparts
                                val = int(val_str.strip())
                                shares[name_key.strip()] = val
                                total_shares += val
                        except Exception:
                            pass
                if total_shares <= 0:
                    anomalies.append({'type': 'warning', 'message': "Share split type specified but shares sum is 0."})

        parsed_rows.append({
            'row_idx': idx,
            'date': date_str,
            'date_parsed': date_obj.isoformat() if date_obj else None,
            'description': desc,
            'paid_by': paid_by,
            'amount': str(amount),
            'currency': curr,
            'exchange_rate': str(rate),
            'converted_amount': str(converted_amount),
            'split_type': split_type or ('settlement' if is_settlement else 'equal'),
            'split_with': split_with_str,
            'split_with_names': split_with_names,
            'split_details': split_details,
            'notes': notes,
            'anomalies': anomalies,
            'action_taken': action_taken,
            'is_settlement': is_settlement
        })
        
    # Unresolved Names detection
    unresolved_names = []
    for name in unique_names_in_csv:
        name_clean = name.lower().strip()
        # Look up by full name or email
        user = user_by_name.get(name_clean) or user_by_email.get(name_clean)
        # Check if they are already in the group
        is_member = False
        if user:
            is_member = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first() is not None
            
        if not user or not is_member:
            unresolved_names.append({
                'csv_name': name,
                'found_user_id': user.id if user else None,
                'found_user_name': user.full_name if user else None,
                'is_member': is_member
            })
            
    # Save parsed data to Flask Session
    session['import_group_id'] = group_id
    session['import_rows'] = parsed_rows
    session['import_unresolved'] = unresolved_names
    
    # Roster of all users for mapping dropdown
    all_users = User.query.order_by(User.full_name).all()

    return render_template(
        'groups/import_review.html',
        group=group,
        parsed_rows=parsed_rows,
        unresolved_names=unresolved_names,
        all_users=all_users
    )

@importer_bp.route('/groups/<int:group_id>/import/confirm', methods=['POST'])
@login_required
def confirm_import(group_id):
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('groups.dashboard'))
        
    group = Group.query.get_or_404(group_id)
    
    # Retrieve state from session
    session_group_id = session.get('import_group_id')
    parsed_rows = session.get('import_rows')
    unresolved_names = session.get('import_unresolved')
    
    if not parsed_rows or session_group_id != group_id:
        flash('Import session expired or invalid. Please upload the CSV again.', 'danger')
        return redirect(url_for('importer.import_csv_view', group_id=group_id))
        
    # Build a name mapping dictionary from form inputs
    name_map = {} # csv_name -> User object
    
    # 1. Resolve registered mapping inputs
    for name_dict in unresolved_names:
        csv_name = name_dict['csv_name']
        action = request.form.get(f'action_{csv_name}') # 'map' or 'create'
        
        if action == 'map':
            mapped_user_id = request.form.get(f'user_id_{csv_name}')
            if mapped_user_id:
                mapped_user = User.query.get(int(mapped_user_id))
                if mapped_user:
                    name_map[csv_name] = mapped_user
                    
                    # Auto-add them to group if not already a member
                    existing_mem = GroupMember.query.filter_by(group_id=group_id, user_id=mapped_user.id).first()
                    if not existing_mem:
                        # Find the first date they appeared in CSV to set joined_at, or default to today
                        new_mem = GroupMember(
                            group_id=group_id,
                            user_id=mapped_user.id,
                            joined_at=datetime.now(timezone.utc).date()
                        )
                        db.session.add(new_mem)
                        
        elif action == 'create':
            # Create a stub user
            email = f"{csv_name.lower().replace(' ', '_').strip()}_{group_id}@example.com"
            # Double check if email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                db_user = existing_user
            else:
                from app import bcrypt
                pwd = bcrypt.generate_password_hash("password123").decode('utf-8')
                db_user = User(
                    full_name=csv_name,
                    email=email,
                    password=pwd
                )
                db.session.add(db_user)
                db.session.flush() # Populate db_user.id
                
            name_map[csv_name] = db_user
            
            # Add them to the group
            existing_mem = GroupMember.query.filter_by(group_id=group_id, user_id=db_user.id).first()
            if not existing_mem:
                new_mem = GroupMember(
                    group_id=group_id,
                    user_id=db_user.id,
                    joined_at=datetime.now(timezone.utc).date()
                )
                db.session.add(new_mem)
                
    # Populate existing group members into the name map
    group_members = GroupMember.query.filter_by(group_id=group_id).all()
    for m in group_members:
        # Map their full name to User
        name_map[m.user.full_name] = m.user
        # Support case-insensitive keying
        name_map[m.user.full_name.lower().strip()] = m.user
        
    # Build list of row indices that the user chose to import
    selected_row_indices = []
    for key, value in request.form.items():
        if key.startswith('row_checked_') and value == 'on':
            try:
                selected_row_indices.append(int(key.replace('row_checked_', '')))
            except ValueError:
                pass
                
    # 2. Iterate and commit rows
    rows_imported = 0
    settlements_imported = 0
    errors = 0
    
    # Process within transaction
    try:
        db.session.flush() # Sync database state for newly added group members
        
        for row in parsed_rows:
            row_idx = row['row_idx']
            if row_idx not in selected_row_indices:
                continue # Skip unselected row
                
            # Fetch dates and descriptions
            date_parsed = datetime.fromisoformat(row['date_parsed']).date() if row['date_parsed'] else None
            if not date_parsed:
                errors += 1
                continue
                
            desc = row['description']
            orig_amt = Decimal(row['amount'])
            curr = row['currency']
            rate = Decimal(row['exchange_rate'])
            converted_amount = Decimal(row['converted_amount'])
            split_type = row['split_type']
            
            # Resolve paid_by
            csv_payer = row['paid_by']
            payer_user = name_map.get(csv_payer) or name_map.get(csv_payer.lower().strip())
            
            if not payer_user:
                errors += 1
                continue
                
            # If it is a settlement
            if row['is_settlement']:
                csv_receiver = row['split_with_names'][0] if row['split_with_names'] else None
                receiver_user = name_map.get(csv_receiver) or name_map.get(csv_receiver.lower().strip()) if csv_receiver else None
                
                if not receiver_user:
                    errors += 1
                    continue
                    
                settlement = Settlement(
                    group_id=group_id,
                    payer_id=payer_user.id,
                    receiver_id=receiver_user.id,
                    amount=converted_amount,
                    original_amount=orig_amt,
                    currency=curr,
                    exchange_rate=rate,
                    date=date_parsed
                )
                db.session.add(settlement)
                settlements_imported += 1
                continue
                
            # Build expense splits
            csv_split_with = row['split_with_names']
            split_users = []
            for name in csv_split_with:
                u = name_map.get(name) or name_map.get(name.lower().strip())
                if u:
                    split_users.append(u)
                    
            if not split_users:
                errors += 1
                continue
                
            # Ensure all split users are active in the group on the expense date
            # To handle this temporal rule gracefully, we check their GroupMember record.
            # If they are not active on that date, we update their joined_at to be <= date_parsed
            # to make sure their membership is historically active!
            for u in split_users:
                member_rec = GroupMember.query.filter_by(group_id=group_id, user_id=u.id).first()
                if member_rec:
                    if member_rec.joined_at > date_parsed:
                        member_rec.joined_at = date_parsed # Extend active membership historically
                    if member_rec.left_at and member_rec.left_at < date_parsed:
                        # Member left before this expense! We remove the left_at constraint or extend it
                        member_rec.left_at = None
            
            # Ensure payer is also active on that date
            payer_rec = GroupMember.query.filter_by(group_id=group_id, user_id=payer_user.id).first()
            if payer_rec:
                if payer_rec.joined_at > date_parsed:
                    payer_rec.joined_at = date_parsed
                if payer_rec.left_at and payer_rec.left_at < date_parsed:
                    payer_rec.left_at = None
                    
            # 3. Calculate Split amounts
            split_amounts = {}
            N = len(split_users)
            sum_computed = Decimal('0.00')
            
            percentages = {}
            shares = {}
            
            if split_type == 'percentage':
                # Parse split details from row
                total_pct = Decimal('0.00')
                raw_pcts = {}
                if row['split_details']:
                    parts = [p.strip() for p in row['split_details'].split(';') if p.strip()]
                    for part in parts:
                        subparts = part.rsplit(' ', 1)
                        if len(subparts) == 2:
                            name, val_str = subparts
                            val = Decimal(val_str.replace('%', '').strip())
                            raw_pcts[name.lower().strip()] = val
                            
                # Match name to user id
                for u in split_users:
                    # check if name maps to user
                    p_val = raw_pcts.get(u.full_name.lower().strip(), Decimal('0.00'))
                    percentages[u.id] = p_val
                    total_pct += p_val
                    
                # Split calculation
                for i, u in enumerate(split_users):
                    if i == N - 1:
                        split_amounts[u.id] = converted_amount - sum_computed
                    else:
                        amt = (converted_amount * percentages[u.id] / Decimal('100.00')).quantize(Decimal('0.01'))
                        split_amounts[u.id] = amt
                        sum_computed += amt
                        
            elif split_type == 'share':
                total_shares = 0
                raw_shares = {}
                if row['split_details']:
                    parts = [p.strip() for p in row['split_details'].split(';') if p.strip()]
                    for part in parts:
                        subparts = part.rsplit(' ', 1)
                        if len(subparts) == 2:
                            name, val_str = subparts
                            val = int(val_str.strip())
                            raw_shares[name.lower().strip()] = val
                            
                for u in split_users:
                    sh_val = raw_shares.get(u.full_name.lower().strip(), 0)
                    shares[u.id] = sh_val
                    total_shares += sh_val
                    
                for i, u in enumerate(split_users):
                    if i == N - 1:
                        split_amounts[u.id] = converted_amount - sum_computed
                    else:
                        amt = (converted_amount * Decimal(str(shares[u.id])) / Decimal(str(total_shares))).quantize(Decimal('0.01'))
                        split_amounts[u.id] = amt
                        sum_computed += amt
                        
            elif split_type == 'unequal':
                # Exact split! e.g., Rohan 700; Priya 400; Meera 400
                total_unequal = Decimal('0.00')
                raw_unequal = {}
                if row['split_details']:
                    parts = [p.strip() for p in row['split_details'].split(';') if p.strip()]
                    for part in parts:
                        subparts = part.rsplit(' ', 1)
                        if len(subparts) == 2:
                            name, val_str = subparts
                            val = Decimal(val_str.strip())
                            raw_unequal[name.lower().strip()] = val
                            
                for u in split_users:
                    val = raw_unequal.get(u.full_name.lower().strip(), Decimal('0.00'))
                    split_amounts[u.id] = val
                    sum_computed += val
                
                # Check for remainder to make sure it matches converted amount exactly
                remainder = converted_amount - sum_computed
                if remainder != 0:
                    split_amounts[split_users[-1].id] += remainder # Adjust on last participant
                    
            else: # Equal split
                base_share = (converted_amount / Decimal(str(N))).quantize(Decimal('0.01'))
                for i, u in enumerate(split_users):
                    if i == N - 1:
                        split_amounts[u.id] = converted_amount - (base_share * Decimal(str(N - 1)))
                    else:
                        split_amounts[u.id] = base_share
                        
            # Insert Expense record
            expense = Expense(
                group_id=group_id,
                paid_by_id=payer_user.id,
                created_by_id=current_user.id,
                description=desc,
                total_amount=converted_amount,
                original_amount=orig_amt,
                currency=curr,
                exchange_rate=rate,
                date=date_parsed,
                split_type=split_type if split_type != 'unequal' else 'exact'
            )
            db.session.add(expense)
            db.session.flush() # Populate expense.id
            
            # Insert Expense splits
            for u in split_users:
                split_rec = ExpenseSplit(
                    expense_id=expense.id,
                    user_id=u.id,
                    amount=split_amounts[u.id],
                    percentage=percentages.get(u.id) if split_type == 'percentage' else None,
                    share=shares.get(u.id) if split_type == 'share' else None
                )
                db.session.add(split_rec)
                
            rows_imported += 1
            
        db.session.commit()
        
        # Clear session
        session.pop('import_group_id', None)
        session.pop('import_rows', None)
        session.pop('import_unresolved', None)
        
        flash(f'Import completed: {rows_imported} expenses and {settlements_imported} settlements imported successfully ({errors} errors skipped).', 'success')
        return redirect(url_for('groups.group_detail', group_id=group_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Import transaction failed: {str(e)}', 'danger')
        return redirect(url_for('importer.import_csv_view', group_id=group_id))
