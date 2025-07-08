# 🎫 CARD WORKFLOW INTEGRATION GUIDE
## Madagascar License System - Card Management

### 📋 **How Cards Are Incorporated**

The system separates **licenses** (lifetime validity) from **cards** (5-year expiry):

```
LICENSE (Lifetime Valid)
├── Card #1 (2024-2029) ← Current
├── Card #2 (2029-2034) ← Future renewal  
└── Card #3 (Replacement if lost/stolen)
```

### 🔄 **Complete Workflow After License Creation**

#### **1. License Creation from Application**
```python
# After application is AUTHORIZED (tests passed)
license = create_license_from_application(
    application_id=app.id,
    restrictions=["01", "03"],  # Corrective lenses + Automatic transmission
    order_card_immediately=True
)

# Results in:
# ✅ License created with number: T01000001231
# ✅ Card created with status: PENDING_PRODUCTION
```

#### **2. Card Production Workflow**
```
PENDING_PRODUCTION → IN_PRODUCTION → READY_FOR_COLLECTION → COLLECTED
```

**A. Send to Printer:**
```python
# When ordering card production
PUT /licenses/cards/{card_id}/status
{
    "status": "IN_PRODUCTION",
    "notes": "Sent to printer batch #2024-001"
}
```

**B. Card Ready:**
```python
# When card is printed and available
PUT /licenses/cards/{card_id}/status  
{
    "status": "READY_FOR_COLLECTION",
    "notes": "Available at Antananarivo office"
}
```

**C. Card Collection:**
```python
# When person collects the card
PUT /licenses/cards/{card_id}/status
{
    "status": "COLLECTED", 
    "collection_reference": "COL-2024-0123",
    "notes": "Collected by license holder with ID verification"
}
```

### 🚫 **Restriction Codes (Applied During Authorization)**

**Driver Restrictions:**
- `01` - Corrective Lenses Required
- `02` - Prosthetics

**Vehicle Restrictions:**  
- `03` - Automatic Transmission Only
- `04` - Electric Powered Only
- `05` - Physical Disabled (Adapted Vehicles)
- `06` - Tractor Only
- `07` - Industrial/Agriculture Only

**Example Authorization Process:**
```python
def authorize_application_with_restrictions(application_id, test_results):
    restrictions = []
    
    # Process test results
    if test_results.requires_corrective_lenses:
        restrictions.append("01")
    
    if test_results.failed_manual_transmission_test:
        restrictions.append("03")
    
    if test_results.physical_disability_accommodation:
        restrictions.append("05")
    
    # Create license with restrictions
    license = create_license_from_application(
        application_id=application_id,
        restrictions=restrictions
    )
    
    return license
```

### 🔧 **Card Management Operations**

#### **View Cards for Collection (Collection Centers)**
```python
GET /licenses/cards?status=READY_FOR_COLLECTION&location_id={location_id}

# Returns cards ready for pickup at specific location
```

#### **Order Replacement Card**
```python
POST /licenses/cards
{
    "license_id": "license-uuid",
    "card_type": "REPLACEMENT", 
    "replacement_reason": "LOST"
}

# Creates new card, marks old card as not current
```

#### **Track Card Expiry**
```python
GET /licenses/cards/near-expiry?days=90

# Returns cards expiring in next 90 days for renewal notifications
```

### 📊 **Dashboard Integration**

**Collection Center Dashboard:**
```python
# What cards are ready for collection today?
ready_cards = get_cards_for_collection(location_id=current_location)

# Show to staff:
for card in ready_cards:
    print(f"License: {card.license.license_number}")
    print(f"Person: {card.license.person.full_name}")  
    print(f"Restrictions: {card.license.restrictions}")
    print(f"Ready since: {card.ready_for_collection_date}")
```

**Renewal Notifications:**
```python
# Check for expiring cards
expiring_cards = get_cards_near_expiry(days_warning=90)

# Send notifications to license holders
for card in expiring_cards:
    send_renewal_notification(
        person=card.license.person,
        card_expiry=card.expiry_date,
        license_number=card.license.license_number
    )
```

### 🎯 **Key Benefits of This Design**

✅ **Separation of Concerns**: License validity vs. physical card expiry  
✅ **Complete History**: Track all cards ever issued for a license  
✅ **Production Tracking**: Monitor card manufacturing process  
✅ **Collection Management**: Efficiently manage card distribution  
✅ **Replacement Handling**: Easy replacement for lost/stolen cards  
✅ **Renewal Workflow**: Automatic expiry tracking and notifications  
✅ **Audit Trail**: Complete history of all card status changes  

### 🚀 **Next Steps**

1. **Run Migration**: `python deploy_license_module_migration.py`
2. **Test License Creation**: Create license from authorized application
3. **Test Card Workflow**: Process card through production stages  
4. **Integrate with Application Flow**: Add restriction determination logic
5. **Set Up Collection Centers**: Configure card collection locations
6. **Implement Renewal Notifications**: Set up automated expiry alerts 