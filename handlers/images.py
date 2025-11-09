"""
Image handling for receipt photos and documents.
"""
import logging
import os
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pdf2image import convert_from_path
from services.skew_detector import get_region_position_name

logger = logging.getLogger(__name__)

# Image storage directory
IMAGES_DIR = Path("images/orig")


async def show_skew_warning(update: Update, status_message, skew_analysis: dict, receipt_id: int) -> None:
    """
    Show skew warning message with user choices.

    Args:
        update: Telegram update object
        status_message: Status message to edit
        skew_analysis: Skew analysis results from skew_detector
        receipt_id: Receipt ID for callback handlers
    """
    max_skew = skew_analysis['max_skew_angle']
    region_index = skew_analysis['max_skew_region']
    num_regions = skew_analysis['num_regions']

    # Get region position name
    region_name = get_region_position_name(region_index, num_regions)

    # Determine tilt direction
    direction = "right" if max_skew > 0 else "left"

    # Build warning message
    warning_text = (
        f"⚠️ SKEW DETECTED\n\n"
        f"Significant skew detected in the {region_name} part of the image.\n\n"
        f"Skew angle: {abs(max_skew):.2f}° (tilted to the {direction})\n"
        f"This may cause incorrect alignment of items and prices during analysis.\n\n"
        f"What would you like to do?"
    )

    # Create inline keyboard with options
    keyboard = [
        [InlineKeyboardButton("🔄 Deskew & Process", callback_data=f"deskew_proceed_{receipt_id}")],
        [InlineKeyboardButton("▶️ Process As-Is", callback_data=f"proceed_skewed_{receipt_id}")],
        [InlineKeyboardButton("🗑️ Discard & Rescan", callback_data=f"skew_discard_{receipt_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await status_message.edit_text(warning_text, reply_markup=reply_markup)
    logger.info(f"Skew warning shown for receipt {receipt_id}: {abs(max_skew):.2f}° in {region_name} region")


def convert_pdf_to_image(pdf_path: str) -> str:
    """
    Convert PDF to image (first page only).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Path to converted image file

    Raises:
        Exception: If PDF conversion fails (e.g., poppler not installed)
    """
    try:
        # Convert first page of PDF to image
        # Note: Requires poppler-utils to be installed on system
        # Ubuntu/Debian: sudo apt-get install poppler-utils
        # WSL: sudo apt install poppler-utils
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=300)

        if not images:
            raise Exception("No pages found in PDF")

        # Save as JPEG
        image_path = pdf_path.replace('.pdf', '.jpg')
        images[0].save(image_path, 'JPEG', quality=95)

        logger.info(f"Converted PDF to image: {pdf_path} -> {image_path}")
        return image_path

    except Exception as e:
        logger.error(f"Error converting PDF to image: {e}")
        if "poppler" in str(e).lower() or "pdftoppm" in str(e).lower():
            logger.error("poppler-utils is not installed. Install with: sudo apt install poppler-utils")
        raise


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos sent by users (camera images)."""
    await process_image(update, context, is_document=False)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos sent as documents (gallery images or PDFs)."""
    mime_type = update.message.document.mime_type

    # Process image documents or PDFs
    if mime_type and (mime_type.startswith('image/') or mime_type == 'application/pdf'):
        await process_image(update, context, is_document=True)
    else:
        await update.message.reply_text('Please send image or PDF files only.')


async def process_image(update: Update, context: ContextTypes.DEFAULT_TYPE, is_document: bool) -> None:
    """
    Process and save receipt image.

    Args:
        update: Telegram update object
        context: Telegram context
        is_document: True if image was sent as document, False if sent as photo
    """
    try:
        # Extract caption (user notes) from message
        user_notes = update.message.caption if update.message.caption else None

        # If no caption, check for recent text message (external app sharing scenario)
        if not user_notes:
            import time
            pending_note = context.user_data.get('pending_user_note')
            if pending_note:
                # Check if the text message was sent within last 10 seconds
                time_diff = time.time() - pending_note['timestamp']
                if time_diff <= 10:
                    user_notes = pending_note['text']
                    logger.info(f"Using preceding text message as user notes (sent {time_diff:.1f}s before image)")
                    # Clear the pending note
                    context.user_data.pop('pending_user_note', None)
                else:
                    logger.debug(f"Ignoring old text message (sent {time_diff:.1f}s ago)")
                    context.user_data.pop('pending_user_note', None)

        if user_notes:
            logger.info(f"User provided notes: {user_notes[:100]}...")

        # Get the file object
        if is_document:
            file = await update.message.document.get_file()
            file_size = update.message.document.file_size
            mime_type = update.message.document.mime_type
        else:
            # For photos, get the largest available size
            photo = update.message.photo[-1]
            file = await photo.get_file()
            file_size = photo.file_size
            mime_type = 'image/jpeg'

        # Create images directory if it doesn't exist
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        user_id = update.effective_user.id
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = Path(file.file_path).suffix or '.jpg'
        filename = f"{user_id}_{timestamp}{file_extension}"
        file_path = IMAGES_DIR / filename

        # Download and save the file
        await file.download_to_drive(file_path)
        logger.info(f"File saved: {file_path}")

        # Delete original message immediately (privacy/security)
        # We have the file saved locally, no need to keep it in Telegram
        original_message_id = update.message.message_id
        chat_id = update.message.chat_id
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=original_message_id)
            logger.info(f"Deleted original message {original_message_id} immediately after download")
        except Exception as delete_error:
            logger.warning(f"Failed to delete original message {original_message_id}: {delete_error}")

        # Convert PDF to image if needed
        is_pdf = mime_type == 'application/pdf'
        if is_pdf:
            try:
                logger.info(f"Converting PDF to image: {file_path}")
                image_path = convert_pdf_to_image(str(file_path))
                file_path = Path(image_path)
                # Update mime_type and file_size for the converted image
                mime_type = 'image/jpeg'
                file_size = os.path.getsize(file_path)
                logger.info(f"PDF converted successfully: {file_path}, size: {file_size}")
            except Exception as e:
                logger.error(f"Failed to convert PDF: {e}")
                await update.message.reply_text(
                    '❌ Sorry, failed to convert PDF. Please try sending as an image instead.'
                )
                return

        # Get database connection from context
        db = context.bot_data.get('database')
        if not db:
            logger.error("Database connection not available")
            await update.message.reply_text('Error: Database not available.')
            return

        # Save image metadata to database
        image_id = db.insert_image(
            user_id=user_id,
            telegram_file_id=file.file_id,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type
        )

        # Create receipt record with status 'created' and user notes
        receipt_id = db.insert_receipt(
            image_id=image_id,
            user_id=user_id,
            status='created',
            user_notes=user_notes
        )

        logger.info(f"Receipt {receipt_id} created for image {image_id}")

        # Initial confirmation to user
        if is_pdf:
            status_message = await update.message.reply_text(
                '✅ PDF received!\n'
                '📄 Converted to image\n'
                '🔄 Pre-processing image...'
            )
        else:
            status_message = await update.message.reply_text(
                '✅ Image received!\n'
                '🔄 Pre-processing image...'
            )

        # Process the image (crop, grayscale, resize)
        # Skip cropping for PDFs as they are already scanned by the camera app
        image_processor = context.bot_data.get('image_processor')
        if image_processor:
            processed_path = image_processor.process_receipt_image(str(file_path), skip_crop=is_pdf)

            if processed_path:
                # Get file size of processed image
                processed_size = os.path.getsize(processed_path)

                # Update database with processed image info
                db.update_image_processed(image_id, processed_path, processed_size)

                # Update receipt status to 'pre-processed'
                db.update_receipt_status(receipt_id, 'pre-processed')

                logger.info(f"Image {image_id} processed successfully, receipt {receipt_id} status: pre-processed")

                # SKEW DETECTION PHASE
                # Analyze skew after preprocessing
                from services import skew_detector
                from config import Config

                config = context.bot_data.get('config') or Config()

                # Update user: analyzing skew
                await status_message.edit_text(
                    ('✅ PDF received!\n✅ Converted to image\n✅ Pre-processing complete!\n' if is_pdf else '✅ Image received!\n✅ Pre-processing complete!\n') +
                    '🔍 Analyzing image skew...'
                )

                skew_analysis = skew_detector.analyze_image_skew(processed_path)
                max_skew = abs(skew_analysis.get('max_skew_angle', 0.0))

                logger.info(f"Skew analysis for receipt {receipt_id}: max_angle={max_skew:.2f}°")

                # Check if skew exceeds threshold
                if max_skew > config.skew_threshold:
                    # Store analysis data for callback handlers
                    context.user_data['pending_skew_analysis'] = {
                        'receipt_id': receipt_id,
                        'image_id': image_id,
                        'processed_image_path': processed_path,
                        'is_pdf_source': is_pdf,
                        'skew_analysis': skew_analysis
                    }

                    # Show skew warning to user
                    await show_skew_warning(update, status_message, skew_analysis, receipt_id)
                    return  # Pause processing, wait for user decision

                # Skew is minimal, continue with normal flow
                logger.info(f"Skew {max_skew:.2f}° is below threshold {config.skew_threshold}°, continuing")

                # Update user with success
                if is_pdf:
                    await status_message.edit_text(
                        '✅ PDF received!\n'
                        '✅ Converted to image\n'
                        '✅ Pre-processing complete!\n'
                        '📸 Receipt detected and optimized\n'
                        '🤖 Analyzing with AI...'
                    )
                else:
                    await status_message.edit_text(
                        '✅ Image received!\n'
                        '✅ Pre-processing complete!\n'
                        '📸 Receipt detected and optimized\n'
                        '🤖 Analyzing with AI...'
                    )

                # Import here to avoid circular dependency
                from services.receipt_analyzer import analyze_receipt_with_claude

                # Analyze with Claude using processed image
                await analyze_receipt_with_claude(
                    context, db, receipt_id, image_id, processed_path, status_message
                )
            else:
                logger.warning(f"Image processing failed for image {image_id}, using original")

                # Update user with fallback
                if is_pdf:
                    await status_message.edit_text(
                        '✅ PDF received!\n'
                        '✅ Converted to image\n'
                        '⚠️ Using original image\n'
                        '🤖 Analyzing with AI...'
                    )
                else:
                    await status_message.edit_text(
                        '✅ Image received!\n'
                        '⚠️ Using original image\n'
                        '🤖 Analyzing with AI...'
                    )

                # Import here to avoid circular dependency
                from services.receipt_analyzer import analyze_receipt_with_claude

                # Analyze with Claude using original image
                await analyze_receipt_with_claude(
                    context, db, receipt_id, image_id, str(file_path), status_message
                )
        else:
            logger.error("Image processor not available")
            await status_message.edit_text(
                '❌ Image processor not available. Please contact admin.'
            )

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await update.message.reply_text(
            '❌ Sorry, there was an error processing your image. Please try again.'
        )
