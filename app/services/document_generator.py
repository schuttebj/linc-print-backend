"""
Document Generation Service for Madagascar License System
Standardized PDF document generation using ReportLab
"""

import io
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect

logger = logging.getLogger(__name__)

class DocumentTemplate:
    """Base class for document templates"""
    
    def __init__(self, title: str, page_size=A4):
        self.title = title
        self.page_size = page_size
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom styles for Madagascar documents"""
        
        # Government header style - National level
        self.styles.add(ParagraphStyle(
            name='GovernmentHeader',
            parent=self.styles['Heading1'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=3,
            textColor=colors.black
        ))
        
        # Department header style - Ministry level
        self.styles.add(ParagraphStyle(
            name='DepartmentHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=3,
            textColor=colors.black
        ))
        
        # Office header style - Department level
        self.styles.add(ParagraphStyle(
            name='OfficeHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=colors.black
        ))
        
        # Official title style - Document type
        self.styles.add(ParagraphStyle(
            name='OfficialTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.black,
            borderColor=colors.black,
            borderWidth=2,
            borderPadding=8,
            spaceAfter=12,
            spaceBefore=6
        ))
        
        # Field label style
        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=1
        ))
        
        # Field value style
        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=1
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.black,
            borderColor=colors.black,
            borderWidth=1,
            borderPadding=4,
            spaceAfter=4,
            spaceBefore=2
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=2,
            spaceBefore=1
        ))
        
        # Official stamp style
        self.styles.add(ParagraphStyle(
            name='OfficialStamp',
            parent=self.styles['Normal'],
            fontSize=7,
            fontName='Helvetica-Oblique',
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=3
        ))

class ReceiptTemplate(DocumentTemplate):
    """Receipt document template for Madagascar transactions"""
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        """Generate receipt PDF from transaction data"""
        try:
            logger.info(f"Generating receipt PDF for transaction: {data.get('transaction_number', 'Unknown')}")
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=20*mm,
                leftMargin=20*mm,
                topMargin=20*mm,
                bottomMargin=20*mm,
                title=self.title
            )
            
            story = []
            
            # Government headers with coat of arms placeholder
            story.append(Paragraph(data.get('government_header', 'REPUBLIC OF MADAGASCAR'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'MINISTRY OF TRANSPORT, TOURISM AND METEOROLOGY'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'General Directorate of Land Transport'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 4))
            
            # Separator line
            separator_table = Table([['']], colWidths=[170*mm])
            separator_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(separator_table)
            story.append(Spacer(1, 8))
            
            # Receipt title with official styling
            story.append(Paragraph(data.get('receipt_title', 'OFFICIAL PAYMENT RECEIPT'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 8))
            
            # Receipt details table with official styling
            receipt_details = [
                [
                    Paragraph('<b>Receipt No:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('receipt_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Date & Time:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Transaction No:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('transaction_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Office:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('location', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            receipt_table = Table(receipt_details, colWidths=[40*mm, 45*mm, 35*mm, 50*mm])
            receipt_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(receipt_table)
            story.append(Spacer(1, 8))
            
            # Customer information section with official header
            story.append(Paragraph('BENEFICIARY INFORMATION', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            customer_data = [
                [
                    Paragraph('<b>Full Name:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>ID/Passport Number:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            customer_table = Table(customer_data, colWidths=[50*mm, 120*mm])
            customer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 8))
            
            # Payment items section with official header
            story.append(Paragraph('PAYMENT DETAILS', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            # Build payment items table with simple styling
            payment_data = [
                [
                    Paragraph('<b>Service / Description</b>', self.styles['FieldLabel']),
                    Paragraph(f'<b>Amount ({data.get("currency", "Ariary")})</b>', self.styles['FieldLabel'])
                ]
            ]
            
            # Add items
            items = data.get('items', [])
            for item in items:
                payment_data.append([
                    Paragraph(str(item.get('description', 'N/A')), self.styles['FieldValue']),
                    Paragraph(f"{item.get('amount', 0):,.0f}", self.styles['FieldValue'])
                ])
            
            # Add total row with emphasis
            payment_data.append([
                Paragraph('<b>TOTAL AMOUNT TO PAY</b>', self.styles['FieldLabel']),
                Paragraph(f"<b>{data.get('total_amount', 0):,.0f}</b>", self.styles['FieldLabel'])
            ])
            
            payment_table = Table(payment_data, colWidths=[110*mm, 60*mm])
            payment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            
            story.append(payment_table)
            story.append(Spacer(1, 8))
            
            # Payment method section with official header
            story.append(Paragraph('PAYMENT METHODS', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            payment_method_data = [
                [
                    Paragraph('<b>Payment Method:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('payment_method', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            if data.get('payment_reference'):
                payment_method_data.append([
                    Paragraph('<b>Reference:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('payment_reference')), self.styles['FieldValue'])
                ])
            
            payment_method_data.append([
                Paragraph('<b>Processed by:</b>', self.styles['FieldLabel']),
                Paragraph(str(data.get('processed_by', 'System')), self.styles['FieldValue'])
            ])
            
            payment_method_table = Table(payment_method_data, colWidths=[50*mm, 120*mm])
            payment_method_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            
            story.append(payment_method_table)
            story.append(Spacer(1, 10))
            
            # Official verification stamp area
            story.append(Paragraph('OFFICIAL STAMP AND SIGNATURE', self.styles['OfficialStamp']))
            story.append(Spacer(1, 10))
            
            # Official footer with government branding
            footer_separator = Table([['']], colWidths=[170*mm])
            footer_separator.setStyle(TableStyle([
                ('LINEABOVE', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(footer_separator)
            story.append(Spacer(1, 4))
            
            story.append(Paragraph(data.get('footer', 'République de Madagascar - Reçu Officiel du Gouvernement'), self.styles['Footer']))
            story.append(Paragraph(data.get('validity_note', 'Ce reçu est valide et doit être conservé pour vos dossiers'), self.styles['Footer']))
            story.append(Paragraph(data.get('contact_info', 'Pour assistance: +261 20 22 123 45 | transport@gov.mg'), self.styles['Footer']))
            story.append(Spacer(1, 4))
            story.append(Paragraph('Document generated electronically - No handwritten signature required', self.styles['OfficialStamp']))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Successfully generated receipt PDF ({len(pdf_data)} bytes)")
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating receipt PDF: {e}")
            raise Exception(f"PDF generation failed: {str(e)}")

class CardOrderConfirmationTemplate(DocumentTemplate):
    """Card Order Confirmation template for Madagascar license orders"""
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        """Generate card order confirmation PDF from order data"""
        try:
            logger.info(f"Generating card order confirmation PDF for order: {data.get('order_number', 'Unknown')}")
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=20*mm,
                leftMargin=20*mm,
                topMargin=20*mm,
                bottomMargin=20*mm,
                title=self.title
            )
            
            story = []
            
            # Government headers
            story.append(Paragraph(data.get('government_header', 'REPUBLIC OF MADAGASCAR'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'MINISTRY OF TRANSPORT, TOURISM AND METEOROLOGY'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'General Directorate of Land Transport'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 4))
            
            # Separator line
            separator_table = Table([['']], colWidths=[170*mm])
            separator_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(separator_table)
            story.append(Spacer(1, 8))
            
            # Document title
            story.append(Paragraph(data.get('document_title', 'CARD ORDER CONFIRMATION'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 8))
            
            # Order details table
            order_details = [
                [
                    Paragraph('<b>Order Number:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('order_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Order Date:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('order_date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Card Type:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('card_type', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Urgency:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('urgency_level', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            order_table = Table(order_details, colWidths=[40*mm, 45*mm, 35*mm, 50*mm])
            order_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            story.append(order_table)
            story.append(Spacer(1, 8))
            
            # Section header with full width
            section_header_table = Table([['APPLICANT INFORMATION']], colWidths=[170*mm])
            section_header_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ]))
            story.append(section_header_table)
            story.append(Spacer(1, 4))
            
            customer_data = [
                [
                    Paragraph('<b>Full Name:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>ID/Passport Number:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>License Number:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('license_number', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            customer_table = Table(customer_data, colWidths=[50*mm, 120*mm])
            customer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 8))
            
            # Order status section header with full width
            section_header_table = Table([['ORDER STATUS']], colWidths=[170*mm])
            section_header_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ]))
            story.append(section_header_table)
            story.append(Spacer(1, 4))
            
            status_data = [
                [
                    Paragraph('<b>Current Status:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('order_status', 'PENDING')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Expected Delivery Date:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('expected_delivery', 'To be determined')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Processing Fee:</b>', self.styles['FieldLabel']),
                    Paragraph(f"{data.get('processing_fee', 0):,.0f} {data.get('currency', 'Ariary')}", self.styles['FieldValue'])
                ]
            ]
            
            status_table = Table(status_data, colWidths=[50*mm, 120*mm])
            status_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(status_table)
            story.append(Spacer(1, 8))
            
            # Important notices section header with full width
            section_header_table = Table([['IMPORTANT INFORMATION']], colWidths=[170*mm])
            section_header_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ]))
            story.append(section_header_table)
            story.append(Spacer(1, 4))
            
            # Important notices in a table for consistency
            notices_data = [
                [Paragraph("• Please keep this document until you receive your card", self.styles['FieldValue'])],
                [Paragraph("• The card will be available at the office indicated above", self.styles['FieldValue'])],
                [Paragraph("• Bring this document and your ID when collecting", self.styles['FieldValue'])],
                [Paragraph("• Cards not collected within 3 months will be destroyed", self.styles['FieldValue'])]
            ]
            
            notices_table = Table(notices_data, colWidths=[170*mm])
            notices_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(notices_table)
            
            story.append(Spacer(1, 8))
            
            # Signature area
            story.append(Paragraph('APPLICANT SIGNATURE', self.styles['OfficialStamp']))
            story.append(Spacer(1, 15))
            
            signature_table = Table([['Date: _______________', '']], colWidths=[85*mm, 85*mm])
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 20),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(signature_table)
            story.append(Spacer(1, 10))
            
            # Footer
            footer_separator = Table([['']], colWidths=[170*mm])
            footer_separator.setStyle(TableStyle([
                ('LINEABOVE', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(footer_separator)
            story.append(Spacer(1, 4))
            
            story.append(Paragraph(data.get('footer', 'République de Madagascar - Confirmation Officielle de Commande'), self.styles['Footer']))
            story.append(Paragraph(data.get('contact_info', 'Pour assistance: +261 20 22 123 45 | transport@gov.mg'), self.styles['Footer']))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Successfully generated card order confirmation PDF ({len(pdf_data)} bytes)")
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating card order confirmation PDF: {e}")
            raise Exception(f"Card order confirmation generation failed: {str(e)}")


class LicenseVerificationTemplate(DocumentTemplate):
    """License Verification Document template for Madagascar license verification"""
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        """Generate license verification PDF from license data"""
        try:
            logger.info(f"Generating license verification PDF for person: {data.get('person_name', 'Unknown')}")
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=15*mm,
                leftMargin=15*mm,
                topMargin=15*mm,
                bottomMargin=15*mm,
                title=self.title
            )
            
            story = []
            
            # Government headers
            story.append(Paragraph(data.get('government_header', 'REPUBLIC OF MADAGASCAR'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'MINISTRY OF TRANSPORT'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'License Information Verification Document'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 4))
            
            # Document title
            story.append(Paragraph(data.get('document_title', 'LICENSE VERIFICATION DOCUMENT'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 8))
            
            # Person Information
            story.append(Paragraph('LICENSE HOLDER INFORMATION', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            person_data = [
                [
                    Paragraph('<b>Full Name:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>ID Number:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Date of Birth:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('birth_date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Nationality:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('nationality', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Verification Date:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('verification_date', datetime.now().strftime('%d/%m/%Y'))), self.styles['FieldValue'])
                ]
            ]
            
            person_table = Table(person_data, colWidths=[60*mm, 120*mm])
            person_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ]))
            
            story.append(person_table)
            story.append(Spacer(1, 8))
            
            # Card Eligible Licenses
            card_licenses = data.get('card_eligible_licenses', [])
            story.append(Paragraph(f'LICENSES TO BE PRINTED ON CARD ({len(card_licenses)})', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            license_headers = [
                [
                    Paragraph('<b>Category</b>', self.styles['FieldLabel']),
                    Paragraph('<b>Status</b>', self.styles['FieldLabel']),
                    Paragraph('<b>Issue Date</b>', self.styles['FieldLabel']),
                    Paragraph('<b>Restrictions</b>', self.styles['FieldLabel'])
                ]
            ]
            
            license_data = []
            for license in card_licenses:
                restrictions_text = self._format_restrictions(license.get('restrictions', {}))
                license_data.append([
                    Paragraph(str(license.get('category', 'N/A')), self.styles['FieldValue']),
                    Paragraph(str(license.get('status', 'N/A')), self.styles['FieldValue']),
                    Paragraph(str(license.get('issue_date', 'N/A')), self.styles['FieldValue']),
                    Paragraph(restrictions_text, self.styles['FieldValue'])
                ])
            
            license_table_data = license_headers + license_data
            license_table = Table(license_table_data, colWidths=[45*mm, 35*mm, 40*mm, 60*mm])
            license_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
            ]))
            
            story.append(license_table)
            story.append(Spacer(1, 8))
            
            # Learners Permits if any
            learners_permits = data.get('learners_permits', [])
            if learners_permits:
                story.append(Paragraph(f'LEARNER\'S PERMITS (NOT PRINTED ON CARD) ({len(learners_permits)})', self.styles['SectionHeader']))
                story.append(Spacer(1, 4))
                
                learners_headers = [
                    [
                        Paragraph('<b>Category</b>', self.styles['FieldLabel']),
                        Paragraph('<b>Status</b>', self.styles['FieldLabel']),
                        Paragraph('<b>Issue Date</b>', self.styles['FieldLabel']),
                        Paragraph('<b>Expiry Date</b>', self.styles['FieldLabel'])
                    ]
                ]
                
                learners_data = []
                for permit in learners_permits:
                    learners_data.append([
                        Paragraph(str(permit.get('category', 'N/A')), self.styles['FieldValue']),
                        Paragraph(str(permit.get('status', 'N/A')), self.styles['FieldValue']),
                        Paragraph(str(permit.get('issue_date', 'N/A')), self.styles['FieldValue']),
                        Paragraph(str(permit.get('expiry_date', 'No expiry')), self.styles['FieldValue'])
                    ])
                
                learners_table_data = learners_headers + learners_data
                learners_table = Table(learners_table_data, colWidths=[45*mm, 35*mm, 45*mm, 55*mm])
                learners_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
                ]))
                
                story.append(learners_table)
                story.append(Spacer(1, 8))
            
            # Signature section
            story.append(Paragraph('LICENSE HOLDER CONFIRMATION', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            confirmation_text = "I confirm that all the information above is accurate and I authorize the printing of my driver's license card with the categories and restrictions listed above."
            story.append(Paragraph(confirmation_text, self.styles['FieldValue']))
            story.append(Spacer(1, 8))
            
            signature_data = [
                [
                    Paragraph('<b>License Holder Signature:</b>', self.styles['FieldLabel']),
                    Paragraph('_____________________________', self.styles['FieldValue']),
                    Paragraph('<b>Date:</b>', self.styles['FieldLabel']),
                    Paragraph('_______________', self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Authorized Officer:</b>', self.styles['FieldLabel']),
                    Paragraph('_____________________________', self.styles['FieldValue']),
                    Paragraph('<b>Badge:</b>', self.styles['FieldLabel']),
                    Paragraph('_______________', self.styles['FieldValue'])
                ]
            ]
            
            signature_table = Table(signature_data, colWidths=[50*mm, 70*mm, 30*mm, 30*mm])
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 15),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(signature_table)
            story.append(Spacer(1, 10))
            
            # Footer
            story.append(Paragraph(data.get('footer', 'Ministry of Transport - Republic of Madagascar'), self.styles['Footer']))
            story.append(Paragraph('License Information System', self.styles['Footer']))
            story.append(Paragraph('This document must be signed before card printing authorization', self.styles['Footer']))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Successfully generated license verification PDF ({len(pdf_data)} bytes)")
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error generating license verification PDF: {e}")
            raise Exception(f"License verification generation failed: {str(e)}")
    
    def _format_restrictions(self, restrictions: Dict[str, Any]) -> str:
        """Format restrictions for display"""
        if not restrictions or not any(restrictions.values()):
            return "00 - None"
        
        formatted = []
        for restriction_type, codes in restrictions.items():
            if codes and isinstance(codes, list):
                for code in codes:
                    formatted.append(f"{restriction_type.replace('_', ' ')}: {code}")
        
        return " | ".join(formatted) if formatted else "00 - None"


class DocumentGenerator:
    """Main document generator service"""
    
    def __init__(self):
        self.version = "1.0.0"
        logger.info("Document Generator Service initialized")
    
    def generate_receipt(self, data: Dict[str, Any]) -> bytes:
        """Generate receipt PDF"""
        template = ReceiptTemplate("Madagascar Official Receipt")
        return template.generate(data)
    
    def generate_card_order_confirmation(self, data: Dict[str, Any]) -> bytes:
        """Generate card order confirmation PDF"""
        template = CardOrderConfirmationTemplate("Madagascar Card Order Confirmation")
        return template.generate(data)
    
    def generate_license_verification(self, data: Dict[str, Any]) -> bytes:
        """Generate license verification PDF"""
        template = LicenseVerificationTemplate("Madagascar License Verification")
        return template.generate(data)
    
    def get_supported_templates(self) -> List[str]:
        """Get list of supported template types"""
        return ["receipt", "card_order_confirmation", "license_verification"]
    
    def generate_document(self, template_type: str, data: Dict[str, Any]) -> bytes:
        """Generate document by template type"""
        if template_type == "receipt":
            return self.generate_receipt(data)
        elif template_type == "card_order_confirmation":
            return self.generate_card_order_confirmation(data)
        elif template_type == "license_verification":
            return self.generate_license_verification(data)
        else:
            raise ValueError(f"Unsupported template type: {template_type}")
    
    def get_sample_receipt_data(self) -> Dict[str, Any]:
        """Generate sample receipt data for testing"""
        return {
            'government_header': 'REPUBLIC OF MADAGASCAR',
            'department_header': 'MINISTRY OF TRANSPORT, TOURISM AND METEOROLOGY',
            'office_header': 'General Directorate of Land Transport',
            'receipt_title': 'OFFICIAL PAYMENT RECEIPT',
            'receipt_number': f'RCT-{datetime.now().strftime("%Y%m%d")}-001',
            'transaction_number': f'TXN-{datetime.now().strftime("%Y%m%d")}-001',
            'date': datetime.now().strftime('%d/%m/%Y at %H:%M'),
            'location': 'Central Office Antananarivo',
            'person_name': 'RAKOTOARISOA Jean Baptiste',
            'person_id': '101 234 567 890',
            'currency': 'Ariary',
            'items': [
                {
                    'description': 'Driver\'s License Application Fee',
                    'amount': 38000
                },
                {
                    'description': 'Theory Examination Fee',
                    'amount': 10000
                },
                {
                    'description': 'Practical Examination Fee',
                    'amount': 10000
                }
            ],
            'total_amount': 58000,
            'payment_method': 'Cash',
            'payment_reference': None,
            'processed_by': 'ANDRIANJAFY Marie Celestine',
            'footer': 'Republic of Madagascar - Official Government Receipt',
            'validity_note': 'This receipt is valid and must be kept for your records',
            'contact_info': 'For assistance: +261 20 22 123 45 | transport@gov.mg'
        }
    
    def get_sample_card_order_data(self) -> Dict[str, Any]:
        """Generate sample card order confirmation data for testing"""
        return {
            'government_header': 'REPUBLIC OF MADAGASCAR',
            'department_header': 'MINISTRY OF TRANSPORT, TOURISM AND METEOROLOGY',
            'office_header': 'General Directorate of Land Transport',
            'document_title': 'CARD ORDER CONFIRMATION',
            'order_number': f'CMD-{datetime.now().strftime("%Y%m%d")}-001',
            'order_date': datetime.now().strftime('%d/%m/%Y at %H:%M'),
            'card_type': 'Standard Driver\'s License',
            'urgency_level': 'Normal (15 business days)',
            'person_name': 'RAKOTOARISOA Jean Baptiste',
            'person_id': '101 234 567 890',
            'license_number': 'MDG-2024-AB-123456',
            'order_status': 'PROCESSING',
            'expected_delivery': '15/02/2024',
            'processing_fee': 5000,
            'currency': 'Ariary',
            'footer': 'Republic of Madagascar - Official Order Confirmation',
            'contact_info': 'For assistance: +261 20 22 123 45 | transport@gov.mg'
        }
    
    def get_sample_license_verification_data(self) -> Dict[str, Any]:
        """Generate sample license verification data for testing"""
        return {
            'government_header': 'REPUBLIC OF MADAGASCAR',
            'department_header': 'MINISTRY OF TRANSPORT',
            'office_header': 'License Information Verification Document',
            'document_title': 'LICENSE VERIFICATION DOCUMENT',
            'person_name': 'RAKOTOARISOA Jean Baptiste',
            'person_id': '101 234 567 890',
            'birth_date': '15/03/1990',
            'nationality': 'Malagasy',
            'verification_date': datetime.now().strftime('%d/%m/%Y'),
            'card_eligible_licenses': [
                {
                    'category': 'A1',
                    'status': 'ACTIVE',
                    'issue_date': '10/01/2022',
                    'restrictions': {
                        'driver_restrictions': ['01'],
                        'vehicle_restrictions': []
                    }
                },
                {
                    'category': 'B',
                    'status': 'ACTIVE',
                    'issue_date': '15/06/2023',
                    'restrictions': {}
                }
            ],
            'learners_permits': [
                {
                    'category': 'A2',
                    'status': 'ACTIVE',
                    'issue_date': '20/11/2023',
                    'expiry_date': '20/11/2024'
                }
            ],
            'footer': 'Ministry of Transport - Republic of Madagascar',
            'contact_info': 'For assistance: +261 20 22 123 45 | transport@gov.mg'
        }
    
    def get_sample_data(self, template_type: str) -> Dict[str, Any]:
        """Get sample data for any template type"""
        if template_type == "receipt":
            return self.get_sample_receipt_data()
        elif template_type == "card_order_confirmation":
            return self.get_sample_card_order_data()
        elif template_type == "license_verification":
            return self.get_sample_license_verification_data()
        else:
            raise ValueError(f"Unsupported template type: {template_type}")

# Service instance
document_generator = DocumentGenerator()
