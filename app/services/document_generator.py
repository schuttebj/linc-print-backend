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
            story.append(Paragraph(data.get('government_header', 'REPOBLIKAN\'I MADAGASIKARA'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'MINISTÈRE DES TRANSPORTS, DU TOURISME ET DE LA MÉTÉOROLOGIE'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'Direction Générale des Transports Terrestres'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 4))
            
            # Separator line
            separator_table = Table([['']], colWidths=[170*mm])
            separator_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(separator_table)
            story.append(Spacer(1, 8))
            
            # Receipt title with official styling
            story.append(Paragraph(data.get('receipt_title', 'REÇU OFFICIEL DE PAIEMENT'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 8))
            
            # Receipt details table with official styling
            receipt_details = [
                [
                    Paragraph('<b>N° de Reçu:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('receipt_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Date & Heure:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>N° de Transaction:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('transaction_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Bureau:</b>', self.styles['FieldLabel']),
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
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            
            story.append(receipt_table)
            story.append(Spacer(1, 8))
            
            # Customer information section with official header
            story.append(Paragraph('INFORMATIONS DU BÉNÉFICIAIRE', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            customer_data = [
                [
                    Paragraph('<b>Nom et Prénoms:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Numéro CIN/Passeport:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            customer_table = Table(customer_data, colWidths=[50*mm, 120*mm])
            customer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 8))
            
            # Payment items section with official header
            story.append(Paragraph('DÉTAIL DES PAIEMENTS', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            # Build payment items table with simple styling
            payment_data = [
                [
                    Paragraph('<b>Service / Prestation</b>', self.styles['FieldLabel']),
                    Paragraph(f'<b>Montant ({data.get("currency", "Ariary")})</b>', self.styles['FieldLabel'])
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
                Paragraph('<b>MONTANT TOTAL À PAYER</b>', self.styles['FieldLabel']),
                Paragraph(f"<b>{data.get('total_amount', 0):,.0f}</b>", self.styles['FieldLabel'])
            ])
            
            payment_table = Table(payment_data, colWidths=[110*mm, 60*mm])
            payment_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            
            story.append(payment_table)
            story.append(Spacer(1, 8))
            
            # Payment method section with official header
            story.append(Paragraph('MODALITÉS DE PAIEMENT', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            payment_method_data = [
                [
                    Paragraph('<b>Mode de Paiement:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('payment_method', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            if data.get('payment_reference'):
                payment_method_data.append([
                    Paragraph('<b>Référence:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('payment_reference')), self.styles['FieldValue'])
                ])
            
            payment_method_data.append([
                Paragraph('<b>Traité par:</b>', self.styles['FieldLabel']),
                Paragraph(str(data.get('processed_by', 'Système')), self.styles['FieldValue'])
            ])
            
            payment_method_table = Table(payment_method_data, colWidths=[50*mm, 120*mm])
            payment_method_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            
            story.append(payment_method_table)
            story.append(Spacer(1, 10))
            
            # Official verification stamp area
            story.append(Paragraph('CACHET ET SIGNATURE OFFICIELS', self.styles['OfficialStamp']))
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
            story.append(Paragraph('Document généré électroniquement - Aucune signature manuscrite requise', self.styles['OfficialStamp']))
            
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
            story.append(Paragraph(data.get('government_header', 'REPOBLIKAN\'I MADAGASIKARA'), self.styles['GovernmentHeader']))
            story.append(Paragraph(data.get('department_header', 'MINISTÈRE DES TRANSPORTS, DU TOURISME ET DE LA MÉTÉOROLOGIE'), self.styles['DepartmentHeader']))
            story.append(Paragraph(data.get('office_header', 'Direction Générale des Transports Terrestres'), self.styles['OfficeHeader']))
            story.append(Spacer(1, 4))
            
            # Separator line
            separator_table = Table([['']], colWidths=[170*mm])
            separator_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(separator_table)
            story.append(Spacer(1, 8))
            
            # Document title
            story.append(Paragraph(data.get('document_title', 'CONFIRMATION DE COMMANDE DE CARTE'), self.styles['OfficialTitle']))
            story.append(Spacer(1, 8))
            
            # Order details table
            order_details = [
                [
                    Paragraph('<b>N° de Commande:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('order_number', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Date de Commande:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('order_date', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Type de Carte:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('card_type', 'N/A')), self.styles['FieldValue']),
                    Paragraph('<b>Urgence:</b>', self.styles['FieldLabel']),
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
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            
            story.append(order_table)
            story.append(Spacer(1, 8))
            
            # Customer information
            story.append(Paragraph('INFORMATIONS DU DEMANDEUR', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            customer_data = [
                [
                    Paragraph('<b>Nom et Prénoms:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_name', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Numéro CIN/Passeport:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('person_id', 'N/A')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>N° de Permis:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('license_number', 'N/A')), self.styles['FieldValue'])
                ]
            ]
            
            customer_table = Table(customer_data, colWidths=[50*mm, 120*mm])
            customer_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 8))
            
            # Order status
            story.append(Paragraph('STATUT DE LA COMMANDE', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            status_data = [
                [
                    Paragraph('<b>Statut Actuel:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('order_status', 'EN ATTENTE')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Date Prévue de Livraison:</b>', self.styles['FieldLabel']),
                    Paragraph(str(data.get('expected_delivery', 'À déterminer')), self.styles['FieldValue'])
                ],
                [
                    Paragraph('<b>Frais de Traitement:</b>', self.styles['FieldLabel']),
                    Paragraph(f"{data.get('processing_fee', 0):,.0f} {data.get('currency', 'Ariary')}", self.styles['FieldValue'])
                ]
            ]
            
            status_table = Table(status_data, colWidths=[50*mm, 120*mm])
            status_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(status_table)
            story.append(Spacer(1, 8))
            
            # Important notices
            story.append(Paragraph('INFORMATIONS IMPORTANTES', self.styles['SectionHeader']))
            story.append(Spacer(1, 4))
            
            notices = [
                "• Veuillez conserver ce document jusqu'à la réception de votre carte",
                "• La carte sera disponible au bureau indiqué ci-dessus",
                "• Apportez ce document et votre CIN lors de la récupération",
                "• Les cartes non récupérées dans les 3 mois seront détruites"
            ]
            
            for notice in notices:
                story.append(Paragraph(notice, self.styles['FieldValue']))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 8))
            
            # Signature area
            story.append(Paragraph('SIGNATURE DU DEMANDEUR', self.styles['OfficialStamp']))
            story.append(Spacer(1, 15))
            
            signature_table = Table([['Date: _______________', 'Signature: _______________']], colWidths=[85*mm, 85*mm])
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
    
    def get_supported_templates(self) -> List[str]:
        """Get list of supported template types"""
        return ["receipt", "card_order_confirmation"]
    
    def generate_document(self, template_type: str, data: Dict[str, Any]) -> bytes:
        """Generate document by template type"""
        if template_type == "receipt":
            return self.generate_receipt(data)
        elif template_type == "card_order_confirmation":
            return self.generate_card_order_confirmation(data)
        else:
            raise ValueError(f"Unsupported template type: {template_type}")
    
    def get_sample_receipt_data(self) -> Dict[str, Any]:
        """Generate sample receipt data for testing"""
        return {
            'government_header': 'REPOBLIKAN\'I MADAGASIKARA',
            'department_header': 'MINISTÈRE DES TRANSPORTS, DU TOURISME ET DE LA MÉTÉOROLOGIE',
            'office_header': 'Direction Générale des Transports Terrestres',
            'receipt_title': 'REÇU OFFICIEL DE PAIEMENT',
            'receipt_number': f'RCT-{datetime.now().strftime("%Y%m%d")}-001',
            'transaction_number': f'TXN-{datetime.now().strftime("%Y%m%d")}-001',
            'date': datetime.now().strftime('%d/%m/%Y à %H:%M'),
            'location': 'Bureau Central Antananarivo',
            'person_name': 'RAKOTOARISOA Jean Baptiste',
            'person_id': '101 234 567 890',
            'currency': 'Ariary',
            'items': [
                {
                    'description': 'Frais de demande de permis de conduire',
                    'amount': 38000
                },
                {
                    'description': 'Examen théorique',
                    'amount': 10000
                },
                {
                    'description': 'Examen pratique',
                    'amount': 10000
                }
            ],
            'total_amount': 58000,
            'payment_method': 'Espèces',
            'payment_reference': None,
            'processed_by': 'ANDRIANJAFY Marie Célestine',
            'footer': 'République de Madagascar - Reçu Officiel du Gouvernement',
            'validity_note': 'Ce reçu est valide et doit être conservé pour vos dossiers',
            'contact_info': 'Pour assistance: +261 20 22 123 45 | transport@gov.mg'
        }
    
    def get_sample_card_order_data(self) -> Dict[str, Any]:
        """Generate sample card order confirmation data for testing"""
        return {
            'government_header': 'REPOBLIKAN\'I MADAGASIKARA',
            'department_header': 'MINISTÈRE DES TRANSPORTS, DU TOURISME ET DE LA MÉTÉOROLOGIE',
            'office_header': 'Direction Générale des Transports Terrestres',
            'document_title': 'CONFIRMATION DE COMMANDE DE CARTE',
            'order_number': f'CMD-{datetime.now().strftime("%Y%m%d")}-001',
            'order_date': datetime.now().strftime('%d/%m/%Y à %H:%M'),
            'card_type': 'Permis de Conduire Standard',
            'urgency_level': 'Normal (15 jours ouvrables)',
            'person_name': 'RAKOTOARISOA Jean Baptiste',
            'person_id': '101 234 567 890',
            'license_number': 'MDG-2024-AB-123456',
            'order_status': 'EN COURS DE TRAITEMENT',
            'expected_delivery': '15/02/2024',
            'processing_fee': 5000,
            'currency': 'Ariary',
            'footer': 'République de Madagascar - Confirmation Officielle de Commande',
            'contact_info': 'Pour assistance: +261 20 22 123 45 | transport@gov.mg'
        }
    
    def get_sample_data(self, template_type: str) -> Dict[str, Any]:
        """Get sample data for any template type"""
        if template_type == "receipt":
            return self.get_sample_receipt_data()
        elif template_type == "card_order_confirmation":
            return self.get_sample_card_order_data()
        else:
            raise ValueError(f"Unsupported template type: {template_type}")

# Service instance
document_generator = DocumentGenerator()
