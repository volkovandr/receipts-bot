"""
Image handling for receipt photos and documents.
"""
import logging
import os
from pathlib import Path
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

# Image storage directory
IMAGES_DIR = Path("images/orig")


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

        # Create receipt record with status 'created'
        receipt_id = db.insert_receipt(
            image_id=image_id,
            user_id=user_id,
            status='created'
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
