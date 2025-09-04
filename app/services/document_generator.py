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
        
        # Government header style
        self.styles.add(ParagraphStyle(
            name='GovernmentHeader',
            parent=self.styles['Heading1'],
            fontSize=18,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=colors.black
        ))
        
        # Department header style
        self.styles.add(ParagraphStyle(
            name='DepartmentHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=colors.black
        ))
        
        # Office header style
        self.styles.add(ParagraphStyle(
            name='OfficeHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.black
        ))
        
        # Official title style
        self.styles.add(ParagraphStyle(
            name='OfficialTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.blue,
            borderColor=colors.black,
            borderWidth=2,
            borderPadding=8,
            backColor=colors.lightgrey,
            spaceAfter=12
        ))
        
        # Field label style
        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            textColor=colors.black
        ))
        
        # Field value style
        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            alignment=TA_LEFT,
            textColor=colors.black
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=6
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
            
            # Government headers
            story.append(Paragraph(data.get('government_header', 'REPOBLIKAN\'I MADAGASIKARA'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'Ministry of Transport'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'Driver License Department'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 12))
            
            # Receipt title with border
            story.append(Paragraph(data.get('receipt_title', 'OFFICIAL RECEIPT'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 20))
            
            # Receipt details table
            receipt_details = [
                [
                    Paragraph('<b>Receipt No:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('receipt_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Date:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Transaction No:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('transaction_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Location:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('location', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            receipt_table = Table(receipt_details, colWidths=[35*mm, 50*mm, 25*mm, 60*mm])
            receipt_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            
            story.append(receipt_table)
            story.append(Spacer(1, 20))
            
            # Customer information box
            story.append(Paragraph('<b>Customer Information</b>', self.styles['FieldLabel']))
            story.append(Spacer(1, 6))
            
            customer_data = [
                [
                    Paragraph('<b>Name:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>ID Number:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            customer_table = Table(customer_data, colWidths=[40*mm, 130*mm])
            customer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 20))
            
            # Payment items table
            story.append(Paragraph('<b>Payment Details</b>', self.styles['FieldLabel']))
            story.append(Spacer(1, 6))
            
            # Build payment items table
            payment_data = [
                [
                    Paragraph('<b>Description</b>', self.styles['FieldLabel']),
                    Paragraph(f'<b>Amount ({data.get("currency", "MGA")})</b>', self.styles['FieldLabel'])
                ]
            ]
            
            # Add items
            items = data.get('items', [])
            for item in items:
                payment_data.append([
                    Paragraph(str(item.get('description', 'N/A')), self.styles['FieldValue']),
                    Paragraph(f"{item.get('amount', 0):,.2f}", self.styles['FieldValue'])
                ])
            
            # Add total row
            payment_data.append([
                Paragraph('<b>TOTAL</b>', self.styles['FieldLabel']),
                Paragraph(f"<b>{data.get('total_amount', 0):,.2f}</b>", self.styles['FieldLabel'])
            ])
            
            payment_table = Table(payment_data, colWidths=[120*mm, 50*mm])
            payment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(payment_table)
            story.append(Spacer(1, 20))
            
            # Payment method information
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
                Paragraph('<b>Processed By:</b>', self.styles['FieldLabel']),
                Paragraph(str(data.get('processed_by', 'System')), self.styles['FieldValue'])
            ])
            
            payment_method_table = Table(payment_method_data, colWidths=[40*mm, 130*mm])
            payment_method_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
                ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(payment_method_table)
            story.append(Spacer(1, 30))
            
            # Footer
            story.append(Paragraph(data.get('footer', 'This is an official receipt from the Madagascar Government'), self.styles['Footer']))
            story.append(Paragraph(data.get('validity_note', 'This receipt is valid for official transactions'), self.styles['Footer']))
            story.append(Paragraph(data.get('contact_info', 'For inquiries, contact your local license office'), self.styles['Footer']))
            
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

class DocumentGenerator:
    """Main document generator service"""
    
    def __init__(self):
        self.version = "1.0.0"
        logger.info("Document Generator Service initialized")
    
    def generate_receipt(self, data: Dict[str, Any]) -> bytes:
        """Generate receipt PDF"""
        template = ReceiptTemplate("Madagascar Official Receipt")
        return template.generate(data)
    
    def get_sample_receipt_data(self) -> Dict[str, Any]:
        """Generate sample receipt data for testing"""
        return {
            'government_header': 'REPOBLIKAN\'I MADAGASIKARA',
            'department_header': 'MINISTRY OF TRANSPORT',
            'office_header': 'DRIVER LICENSE DEPARTMENT',
            'receipt_title': 'OFFICIAL PAYMENT RECEIPT',
            'receipt_number': f'RCT-{datetime.now().strftime("%Y%m%d")}-001',
            'transaction_number': f'TXN-{datetime.now().strftime("%Y%m%d")}-001',
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'location': 'Antananarivo Central Office',
            'person_name': 'RAKOTO Jean Pierre',
            'person_id': '101234567890',
            'currency': 'MGA',
            'items': [
                {
                    'description': 'Driver License Application Fee',
                    'amount': 38000.00
                },
                {
                    'description': 'Theory Test Fee',
                    'amount': 10000.00
                },
                {
                    'description': 'Practical Test Fee',
                    'amount': 10000.00
                }
            ],
            'total_amount': 58000.00,
            'payment_method': 'Cash',
            'payment_reference': None,
            'processed_by': 'Maria ANDRIANAIVO',
            'footer': 'Republic of Madagascar - Official Government Receipt',
            'validity_note': 'This receipt is valid and must be retained for your records',
            'contact_info': 'For assistance: +261 20 22 123 45 | info@transport.gov.mg'
        }

# Service instance
document_generator = DocumentGenerator()
