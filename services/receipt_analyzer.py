"""
Receipt analysis service using Claude AI.
"""
import logging
from services.receipt_formatter import format_receipt_summary

logger = logging.getLogger(__name__)


async def analyze_receipt_with_claude(context, db, receipt_id, image_id, image_path, status_message):
    """
    Analyze receipt with Claude AI and save results to database.

    Args:
        context: Telegram context
        db: Database instance
        receipt_id: Receipt ID
        image_id: Image ID
        image_path: Path to image file (processed or original)
        status_message: Telegram message to update with status
    """
    try:
        # Get Claude service from context
        claude_service = context.bot_data.get('claude_service')
        if not claude_service:
            logger.error("Claude service not available")
            await status_message.edit_text(
                '❌ AI service not available. Please contact admin.'
            )
            db.update_receipt_status(receipt_id, 'failed')
            return

        # Update receipt status to 'processing'
        db.update_receipt_status(receipt_id, 'processing')

        # Get categories from database
        categories = db.get_all_categories()
        logger.info(f"Loaded {len(categories)} categories for analysis")

        # Get category notes from database
        category_notes = db.get_categories_with_notes()
        logger.info(f"Loaded {len(category_notes)} category notes for analysis")

        # Analyze receipt with Claude
        receipt_data, input_tokens, output_tokens = claude_service.analyze_receipt(
            image_path, categories, category_notes
        )

        # Extract data from response
        extraction_status = receipt_data.get('extraction_status', 'unknown')
        merchant_data = receipt_data.get('merchant', {})
        transaction_data = receipt_data.get('transaction', {})
        items = receipt_data.get('items', [])
        uncertain_fields = receipt_data.get('uncertain_fields', [])
        need_clarification = receipt_data.get('need_clarification', [])

        # Insert AI analysis record
        ai_analysis_id = db.insert_ai_analysis(
            model_name=context.bot_data['claude_service'].model,
            extraction_status=extraction_status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_data=receipt_data
        )

        # Insert merchant
        merchant_id = db.insert_or_get_merchant(
            name=merchant_data.get('name', 'Unknown'),
            city=merchant_data.get('city'),
            country=merchant_data.get('country'),
            address=merchant_data.get('address'),
            logo_description=merchant_data.get('logo_description')
        )

        # Insert transaction
        transaction_id = db.insert_transaction(
            date=transaction_data.get('date'),
            time=transaction_data.get('time'),
            currency=transaction_data.get('currency', 'EUR'),
            net_amount=transaction_data.get('net_amount'),
            vat_amount=transaction_data.get('vat_amount'),
            brutto_amount=transaction_data.get('brutto_amount'),
            payment_method=transaction_data.get('payment_method'),
            card_number=transaction_data.get('card_number')
        )

        # Update receipt with analysis results
        db.update_receipt_with_analysis(
            receipt_id=receipt_id,
            merchant_id=merchant_id,
            transaction_id=transaction_id,
            ai_analysis_id=ai_analysis_id
        )

        # Insert receipt items
        if items:
            db.insert_receipt_items(receipt_id, items)

        # Check total consistency
        is_consistent = True
        items_sum = 0.0
        receipt_total = transaction_data.get('brutto_amount')

        if items and receipt_total is not None:
            items_sum = db.get_receipt_items_sum(receipt_id)

            # Compare with tolerance for floating point errors (0.01 currency units)
            if abs(float(receipt_total) - items_sum) > 0.01:
                is_consistent = False
                logger.warning(f"Receipt {receipt_id} total inconsistency: "
                             f"receipt total={receipt_total}, items sum={items_sum}")
                db.update_receipt_status(receipt_id, 'completed/inconsistent')

        logger.info(f"Receipt {receipt_id} analyzed successfully: {len(items)} items, "
                   f"status: {extraction_status}, consistent: {is_consistent}")

        # Get user ID for authorization
        user_id = status_message.chat.id

        # Format receipt summary using the formatter
        try:
            success_text, reply_markup = format_receipt_summary(db, receipt_id, user_id)
            await status_message.edit_text(success_text, reply_markup=reply_markup)
        except ValueError as e:
            logger.error(f"Failed to format receipt summary: {e}")
            await status_message.edit_text(
                '✅ Analysis complete but failed to generate summary!\n'
                f'Receipt ID: {receipt_id}'
            )

    except ValueError as e:
        # Handle specific validation errors (like refusals) with custom messages
        logger.warning(f"Receipt analysis validation error: {e}")

        # Check if it's a refusal error
        error_msg = str(e)
        extraction_status = 'refused' if 'refused to process' in error_msg.lower() else 'failed'

        # Insert AI analysis record for failure
        ai_analysis_id = db.insert_ai_analysis(
            model_name=context.bot_data['claude_service'].model,
            extraction_status=extraction_status,
            input_tokens=0,
            output_tokens=0,
            error_message=error_msg
        )

        # Update receipt with failed analysis
        db.update_receipt_with_analysis(
            receipt_id=receipt_id,
            merchant_id=None,
            transaction_id=None,
            ai_analysis_id=ai_analysis_id
        )

        # Update receipt status to 'failed'
        db.update_receipt_status(receipt_id, 'failed')

        if 'refused to process' in error_msg.lower():
            await status_message.edit_text(
                '❌ Analysis refused!\n\n'
                'Claude AI declined to process this image. This may happen if:\n'
                '• The image contains credit card numbers\n'
                '• The image contains personal IDs\n'
                '• The image triggers content filters\n\n'
                'Please try:\n'
                '• Covering sensitive information\n'
                '• Taking a clearer photo\n'
                '• Using a different receipt'
            )
        else:
            await status_message.edit_text(
                f'❌ Analysis failed!\n\n'
                f'Error: {error_msg}\n\n'
                'The image has been saved. Please try again.'
            )

    except Exception as e:
        logger.error(f"Error analyzing receipt with Claude: {e}", exc_info=True)

        # Insert AI analysis record for unexpected error
        try:
            ai_analysis_id = db.insert_ai_analysis(
                model_name=context.bot_data['claude_service'].model,
                extraction_status='failed',
                input_tokens=0,
                output_tokens=0,
                error_message=str(e)
            )

            # Update receipt with failed analysis
            db.update_receipt_with_analysis(
                receipt_id=receipt_id,
                merchant_id=None,
                transaction_id=None,
                ai_analysis_id=ai_analysis_id
            )
        except Exception as db_error:
            logger.error(f"Failed to save error to database: {db_error}")

        # Update receipt status to 'failed'
        db.update_receipt_status(receipt_id, 'failed')

        await status_message.edit_text(
            '❌ Analysis failed!\n'
            'The image has been saved, but AI analysis encountered an error.\n'
            'Please try again or contact support.'
        )
