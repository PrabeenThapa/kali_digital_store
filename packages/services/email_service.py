import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from packages.config.config import EnvKeys

logger = logging.getLogger(__name__)

# Default SMTP settings (configurable via environment variables or BotSettings)
SMTP_HOST = EnvKeys._get_optional("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(EnvKeys._get_optional("SMTP_PORT", "587"))
SMTP_USER = EnvKeys._get_optional("SMTP_USER", "")
SMTP_PASSWORD = EnvKeys._get_optional("SMTP_PASSWORD", "")
SMTP_FROM = EnvKeys._get_optional("SMTP_FROM", "KDS Digital Store <no-reply@kdsstore.com>")
SMTP_TLS = EnvKeys._get_optional("SMTP_TLS", "1") == "1"


def format_delivery_template(
    template: Optional[str],
    *,
    customer_email: str,
    product_name: str,
    quantity: int,
    amount_str: str,
    delivered_content: str,
    warranty: str = "",
    note: str = "",
    tx_id: str = "",
) -> str:
    """Format delivery template replacing all placeholder tags."""
    if not template or not template.strip():
        return delivered_content

    rendered = template
    replacements = {
        "{customer_email}": customer_email,
        "{product_name}": product_name,
        "{quantity}": str(quantity),
        "{amount}": amount_str,
        "{credentials}": delivered_content,
        "{keys}": delivered_content,
        "{warranty}": warranty or "Standard store warranty",
        "{note}": note or "Thank you for choosing KDS Digital Store.",
        "{tx_id}": tx_id,
        "{support_contact}": "Telegram: @KaliDigitalSupport",
    }
    for tag, val in replacements.items():
        rendered = rendered.replace(tag, str(val))
    return rendered


def generate_order_delivery_html(
    customer_email: str,
    product_name: str,
    quantity: int,
    amount_str: str,
    delivered_content: str,
    order_id: str = "",
    tx_id: Optional[str] = None,
    custom_template: Optional[str] = None,
    warranty: str = "",
    note: str = "",
) -> str:
    """
    Generate a modern, responsive HTML email for digital goods delivery.
    """
    formatted_body = format_delivery_template(
        custom_template,
        customer_email=customer_email,
        product_name=product_name,
        quantity=quantity,
        amount_str=amount_str,
        delivered_content=delivered_content,
        warranty=warranty,
        note=note,
        tx_id=tx_id or "",
    )

    tx_line = f"""
    <tr>
      <td style="padding: 8px 0; color: #888888; font-size: 13px;">Transaction Ref:</td>
      <td style="padding: 8px 0; color: #ffffff; font-size: 13px; font-weight: bold; font-family: monospace; text-align: right;">{tx_id}</td>
    </tr>
    """ if tx_id else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Your Digital Order - KDS Digital Store</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0b0f19; padding: 40px 15px;">
        <tr>
          <td align="center">
            <table width="100%" max-width="580" cellpadding="0" cellspacing="0" style="max-width: 580px; background-color: #131b2e; border-radius: 24px; border: 1px solid rgba(255, 255, 255, 0.1); overflow: hidden; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);">
              
              <!-- Header -->
              <tr>
                <td style="padding: 35px 30px; background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); text-align: center;">
                  <div style="font-size: 28px; font-weight: 900; color: #ffffff; letter-spacing: -0.5px;">
                    ⚡ KDS DIGITAL STORE
                  </div>
                  <div style="font-size: 13px; font-weight: 600; color: rgba(255, 255, 255, 0.9); margin-top: 5px;">
                    Order Confirmation & Digital Key Delivery
                  </div>
                </td>
              </tr>

              <!-- Main Content -->
              <tr>
                <td style="padding: 30px;">
                  <p style="font-size: 15px; color: #cbd5e1; margin: 0 0 20px 0; line-height: 1.6;">
                    Hello,<br>
                    Thank you for your order! Your digital keys / account credentials have been processed and delivered below:
                  </p>

                  <!-- Order Summary Card -->
                  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 25px;">
                    <tr>
                      <td style="padding: 8px 0; color: #888888; font-size: 13px;">Product:</td>
                      <td style="padding: 8px 0; color: #ffffff; font-size: 14px; font-weight: bold; text-align: right;">{product_name}</td>
                    </tr>
                    <tr>
                      <td style="padding: 8px 0; color: #888888; font-size: 13px;">Quantity:</td>
                      <td style="padding: 8px 0; color: #ffffff; font-size: 13px; font-weight: bold; text-align: right;">{quantity}x</td>
                    </tr>
                    <tr>
                      <td style="padding: 8px 0; color: #888888; font-size: 13px;">Total Paid:</td>
                      <td style="padding: 8px 0; color: #ef4444; font-size: 15px; font-weight: 900; text-align: right;">{amount_str}</td>
                    </tr>
                    {tx_line}
                  </table>

                  <!-- Delivered Credentials / Keys Box -->
                  <div style="font-size: 12px; font-weight: 800; text-transform: uppercase; color: #ef4444; letter-spacing: 1px; margin-bottom: 8px;">
                    🔑 Delivered Keys / Account Credentials:
                  </div>
                  <div style="background-color: #050811; border: 1px solid #ef4444; border-radius: 16px; padding: 20px; font-family: 'Courier New', Courier, monospace; font-size: 14px; font-weight: bold; color: #34d399; line-height: 1.6; white-space: pre-wrap; word-break: break-all; margin-bottom: 25px;">
{formatted_body}
                  </div>

                  <!-- Instructions & Warranty -->
                  <div style="background-color: rgba(239, 68, 68, 0.05); border-left: 4px solid #ef4444; border-radius: 8px; padding: 15px; margin-bottom: 25px;">
                    <div style="font-size: 13px; font-weight: bold; color: #ffffff; margin-bottom: 4px;">
                      🛡️ Warranty & Replacement Guarantee
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; line-height: 1.5;">
                      Please test your account credentials immediately. If you encounter any issues, reply to this email or contact 24/7 support via Telegram.
                    </div>
                  </div>

                  <!-- Action Buttons -->
                  <div style="text-align: center; margin-top: 30px;">
                    <a href="{EnvKeys.WEB_URL}/dashboard" style="display: inline-block; background-color: #ef4444; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 800; padding: 14px 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);">
                      View In Account Dashboard →
                    </a>
                  </div>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="padding: 25px 30px; background-color: #0b0f19; text-align: center; border-top: 1px solid rgba(255, 255, 255, 0.05); font-size: 11px; color: #64748b;">
                  <div>© {datetime_now_year()} KDS Digital Store Nepal. All rights reserved.</div>
                  <div style="margin-top: 6px;">Need help? Contact our support team directly.</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def datetime_now_year():
    from datetime import datetime
    return datetime.now().year


async def send_order_delivery_email(
    customer_email: str,
    product_name: str,
    quantity: int,
    amount_str: str,
    delivered_content: str,
    order_id: str = "",
    tx_id: Optional[str] = None,
    custom_template: Optional[str] = None,
    warranty: str = "",
    note: str = "",
) -> bool:
    """
    Asynchronously send an order delivery email to the customer.
    Runs the SMTP protocol in an executor thread to avoid blocking the event loop.
    """
    if not customer_email or "@" not in customer_email:
        logger.warning(f"Skipping email delivery: invalid email '{customer_email}'")
        return False

    def _sync_send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"⚡ Your Digital Order Delivery: {product_name} - KDS Digital Store"
            msg["From"] = SMTP_FROM
            msg["To"] = customer_email

            # Formatted text
            formatted_text = format_delivery_template(
                custom_template,
                customer_email=customer_email,
                product_name=product_name,
                quantity=quantity,
                amount_str=amount_str,
                delivered_content=delivered_content,
                warranty=warranty,
                note=note,
                tx_id=tx_id or "",
            )

            # Plain text fallback
            plain_text = (
                f"KDS DIGITAL STORE - ORDER DELIVERY\n\n"
                f"Product: {product_name} (x{quantity})\n"
                f"Amount: {amount_str}\n"
                f"{f'Transaction Ref: {tx_id}' if tx_id else ''}\n\n"
                f"Delivered Credentials / Key:\n{formatted_text}\n\n"
                f"Access your account dashboard at {EnvKeys.WEB_URL}/dashboard\n"
            )
            msg.attach(MIMEText(plain_text, "plain"))

            # HTML version
            html_content = generate_order_delivery_html(
                customer_email=customer_email,
                product_name=product_name,
                quantity=quantity,
                amount_str=amount_str,
                delivered_content=delivered_content,
                order_id=order_id,
                tx_id=tx_id,
                custom_template=custom_template,
                warranty=warranty,
                note=note,
            )
            msg.attach(MIMEText(html_content, "html"))

            # If no SMTP_USER or host is dummy, log the dispatch
            if not SMTP_USER or not SMTP_PASSWORD:
                logger.info(
                    f"📧 [EMAIL DISPATCH LOG] To: {customer_email} | Product: {product_name} | Key: {delivered_content[:30]}... "
                    f"(Configure SMTP_USER & SMTP_PASSWORD in .env for live relay)"
                )
                return True

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                if SMTP_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM, [customer_email], msg.as_string())
            
            logger.info(f"✅ Order delivery email successfully sent to {customer_email}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send delivery email to {customer_email}: {e}")
            return False

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_send)
