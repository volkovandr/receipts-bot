# Receipt Editing Feature - Testing Guide

## Prerequisites

1. **Run Database Migration**
   ```bash
   psql -h localhost -U <user> -d <database> -f migrations/001_add_receipt_item_is_deleted.sql
   ```

2. **Verify Migration**
   ```bash
   psql -h localhost -U <user> -d <database> -c "\d app_receipts_bot.receipt_item"
   ```
   Look for: `is_deleted | boolean | | default false`

3. **Start the Bot**
   ```bash
   ./venv/bin/python bot.py
   ```

---

## Test Scenarios

### Test 1: Basic Edit Flow
**Objective**: Verify edit button appears and item list displays

**Steps**:
1. Upload a receipt image
2. Wait for AI analysis to complete
3. Look for three buttons in summary: 🔍 View | ✏️ Edit | 🗑️ Delete
4. Click "✏️ Edit receipt"
5. Verify item list appears with format:
   ```
   📝 Receipt Items (N total)

   1. Item Name
      Category: Category Name
      Price: XX.XX
      [❌] [💰] [🏷️]
   ```

**Expected Result**: Item list shows correctly with action buttons

---

### Test 2: Delete Item
**Objective**: Verify item deletion and summary refresh

**Steps**:
1. From item list, click ❌ button on first item
2. Observe the response

**Expected Result**:
- Message: "✅ Item deleted!"
- Updated summary shown
- Item count reduced by 1
- Total recalculated
- Original receipt total preserved

**Verification**:
```sql
SELECT item_id, item_name, is_deleted
FROM app_receipts_bot.receipt_item
WHERE receipt_id = <receipt_id>;
```
Deleted item should have `is_deleted = TRUE`

---

### Test 3: Edit Amount (Valid Input)
**Objective**: Verify amount editing with valid input

**Steps**:
1. From item list, click 💰 button on an item
2. Bot asks: "Please enter the new amount (e.g., 12.50):"
3. Type a valid amount: `15.99`
4. Send message

**Expected Result**:
- Message: "✅ Amount updated!"
- Item: <name>
- New amount: 15.99
- Updated summary with new total

**Verification**:
```sql
SELECT item_id, item_name, total_price, updated_at
FROM app_receipts_bot.receipt_item
WHERE receipt_id = <receipt_id>;
```
Item should have new `total_price` and newer `updated_at`

---

### Test 4: Edit Amount (Invalid Input)
**Objective**: Verify input validation

**Test Cases**:
1. Type `abc` → Should reject with "Invalid amount format"
2. Type `-5` → Should reject with "Invalid amount" (< 0.01)
3. Type `100000` → Should reject with "Invalid amount" (> 99999.99)
4. Type `12,50` → Should ACCEPT (comma as decimal separator)

**Expected Result**: Proper error messages, valid input accepted

---

### Test 5: Change Category (Match Found)
**Objective**: Verify fuzzy category search

**Steps**:
1. From item list, click 🏷️ button on an item
2. Bot asks: "Please enter category name or keywords to search:"
3. Type: `food`
4. Observe results

**Expected Result**:
- Bot shows: "🔍 Found N matching categories:"
- Lists categories like:
  - Food: Groceries
  - Food: Restaurants
  - Pet: Food
- Each category has ✅ button
- Cancel button at bottom

**Test different search terms**:
- Exact match: `Food: Groceries` → Should rank first
- Partial match: `grocer` → Should find "Food: Groceries"
- Typo: `grocerys` → Should still find "Food: Groceries" (fuzzy)
- No match: `xyz123` → Should offer to create new category

---

### Test 6: Change Category (Select Category)
**Objective**: Verify category assignment

**Steps**:
1. Search for category (e.g., `food`)
2. Click ✅ button on a category
3. Observe response

**Expected Result**:
- Message: "✅ Category updated!"
- Updated summary showing new category breakdown

**Verification**:
```sql
SELECT ri.item_id, ri.item_name, c.category_name
FROM app_receipts_bot.receipt_item ri
LEFT JOIN app_receipts_bot.category c ON ri.category_id = c.category_id
WHERE ri.receipt_id = <receipt_id>;
```

---

### Test 7: Create New Category
**Objective**: Verify new category creation

**Steps**:
1. From category search, type: `baby supplies`
2. Bot says: "No categories found. Would you like to create a new category?"
3. Click "✅ Create \"Baby Supplies\""

**Expected Result**:
- Message: "✅ New category created and assigned!"
- Category: Baby Supplies (title-cased)
- Updated summary

**Verification**:
```sql
SELECT category_id, category_name
FROM app_receipts_bot.category
WHERE category_name = 'Baby Supplies';
```

**Try edge cases**:
- All lowercase: `baby food` → Creates "Baby Food"
- All uppercase: `BABY FOOD` → Creates "Baby Food"
- Duplicate: Try creating same category again → Should fail gracefully

---

### Test 8: Back to Summary Navigation
**Objective**: Verify navigation works

**Steps**:
1. From item list, click "⬅️ Back to summary"
2. Observe response

**Expected Result**: Full receipt summary shown with all three buttons (View, Edit, Delete)

---

### Test 9: Cancel Editing
**Objective**: Verify cancel flow

**Steps**:
1. Start editing amount or category
2. When bot asks for input, click ❌ Cancel button
3. Observe response

**Expected Result**:
- Message: "❌ Editing cancelled."
- Editing state cleared
- Next text message not processed as edit input

---

### Test 10: Total Consistency Check
**Objective**: Verify total mismatch warning

**Scenario A: Edit Creates Mismatch**
1. Upload receipt with matching totals
2. Edit an item amount
3. Observe summary

**Expected**: Warning shows:
```
⚠️ Total mismatch!
   Receipt total: XX.XX
   Items sum: YY.YY
   Difference: ZZ.ZZ
```

**Scenario B: Edit Fixes Mismatch**
1. Upload receipt with mismatched totals
2. Edit amounts to match receipt total
3. Observe summary

**Expected**: No warning shown, totals match

---

### Test 11: Edited Indicator
**Objective**: Verify "(edited)" shows in summary

**Steps**:
1. Upload receipt
2. Don't edit anything → No "(edited)" indicator
3. Edit any item (delete, amount, or category)
4. View summary

**Expected**: Summary ends with "✏️ (edited)" line

**Verification**:
```sql
SELECT item_id, created_at, updated_at
FROM app_receipts_bot.receipt_item
WHERE receipt_id = <receipt_id> AND updated_at > created_at;
```
If any rows returned → "(edited)" should show

---

### Test 12: Authorization
**Objective**: Verify users can only edit their own receipts

**Prerequisites**: Two user accounts in whitelist

**Steps**:
1. User A uploads receipt → Note receipt_id
2. User B tries to edit same receipt_id (manually craft callback data)
3. Observe response

**Expected**: "❌ No items found" or "Access denied"

**Verification**: Check logs for authorization warnings

---

### Test 13: Edge Cases

#### Empty Receipt (All Items Deleted)
1. Upload receipt with 2-3 items
2. Delete all items one by one
3. Observe final summary

**Expected**:
- Total items: 0
- Items sum: 0.00
- Total mismatch warning (if original total > 0)

#### Very Long Item Name
1. Upload receipt with long item name (>50 chars)
2. Try to edit it
3. Verify callback_data doesn't break

#### Special Characters in Item Name
1. Item with special chars: `Müller Milch €2.99`
2. Verify editing works correctly

---

## SQL Queries for Debugging

### View All Items (Including Deleted)
```sql
SELECT
    item_id, item_name, total_price, is_deleted,
    created_at, updated_at
FROM app_receipts_bot.receipt_item
WHERE receipt_id = <receipt_id>
ORDER BY item_id;
```

### View Category Fuzzy Search Results
```sql
SELECT
    category_id, category_name,
    SIMILARITY(LOWER(category_name), LOWER('food')) as sim
FROM app_receipts_bot.category
WHERE SIMILARITY(LOWER(category_name), LOWER('food')) > 0.3
ORDER BY sim DESC
LIMIT 10;
```

### View Receipt Summary Data
```sql
SELECT
    r.receipt_id,
    m.name as merchant,
    t.date,
    t.brutto_amount as receipt_total,
    SUM(ri.total_price) as items_sum,
    t.brutto_amount - SUM(ri.total_price) as difference
FROM app_receipts_bot.receipt r
LEFT JOIN app_receipts_bot.merchant m ON r.merchant_id = m.merchant_id
LEFT JOIN app_receipts_bot.transaction t ON r.transaction_id = t.transaction_id
LEFT JOIN app_receipts_bot.receipt_item ri ON r.receipt_id = ri.receipt_id
WHERE r.receipt_id = <receipt_id> AND ri.is_deleted = FALSE
GROUP BY r.receipt_id, m.name, t.date, t.brutto_amount;
```

### Check for Edited Items
```sql
SELECT
    item_id, item_name,
    created_at, updated_at,
    (updated_at > created_at) as was_edited
FROM app_receipts_bot.receipt_item
WHERE receipt_id = <receipt_id>
ORDER BY item_id;
```

---

## Common Issues & Solutions

### Issue: Edit button doesn't appear
**Solution**: Check that receipt has `ai_analysis_id` set and status is 'completed'

### Issue: Fuzzy search returns no results
**Solution**:
1. Verify pg_trgm extension is enabled:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```
2. Lower similarity threshold in testing: Change 0.3 to 0.1 in `category_repository.py`

### Issue: Total doesn't update after amount edit
**Solution**: Check that `get_receipt_items_sum()` filters `is_deleted = FALSE`

### Issue: User can edit other users' items
**Solution**: Check authorization in repository methods - should include `user_id` verification

### Issue: Conversation state persists between edits
**Solution**: Verify `context.user_data.clear()` is called after edit completion

---

## Performance Testing

### Load Test: Multiple Concurrent Edits
1. Simulate 10 users editing different receipts simultaneously
2. Monitor response times (should be < 500ms)
3. Check for database connection pool exhaustion

### Database Query Performance
```sql
EXPLAIN ANALYZE
SELECT ri.item_id, ri.item_name, c.category_name
FROM app_receipts_bot.receipt_item ri
LEFT JOIN app_receipts_bot.category c ON ri.category_id = c.category_id
JOIN app_receipts_bot.receipt r ON ri.receipt_id = r.receipt_id
WHERE ri.receipt_id = 1 AND r.user_id = 123456 AND ri.is_deleted = FALSE;
```

Expected: Should use indexes, no sequential scans

---

## Success Criteria

✅ All basic workflows complete without errors
✅ Input validation works correctly
✅ Authorization prevents cross-user editing
✅ Totals recalculate correctly
✅ Database migrations applied successfully
✅ No memory leaks or connection pool issues
✅ Error messages are user-friendly
✅ Logs show appropriate audit trail

---

## Reporting Issues

When reporting bugs, include:
1. **Steps to reproduce**
2. **Expected behavior**
3. **Actual behavior**
4. **Receipt ID** (if applicable)
5. **User ID** (if applicable)
6. **Relevant log output**
7. **Database query results** (if applicable)

Example format:
```
**Bug**: Category update fails silently

**Steps**:
1. Upload receipt (ID: 123)
2. Click edit → Change category on item 456
3. Search for "food"
4. Select "Food: Groceries"

**Expected**: Category updated, summary refreshed
**Actual**: No response, category unchanged

**Logs**: [paste relevant logs]
**DB State**: [paste query results]
```
