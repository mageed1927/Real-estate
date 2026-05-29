# Mataa VMS Integration Module

## Overview

The Mataa VMS Integration module provides a comprehensive Vendor Management System (VMS) integration for Odoo, enabling vendors to access real-time operational data through secure API endpoints while maintaining the unified vendor concept where in-house and standard vendor accounts are linked.

## Features

### 1. Unified Vendor Model
- **Standard Vendors**: Main vendor accounts with linked in-house vendors
- **In-House Vendors**: Sub-vendor accounts linked to standard vendors
- **Automatic Balance Calculation**: Real-time balance computation across linked accounts
- **Vendor Type Management**: Clear distinction between vendor types with validation

### 2. VMS API Endpoints
- **Authentication**: JWT-based authentication system
- **Vendor Data Access**: Secure access to vendor-specific information
- **Real-time Data**: Live updates for balances, stock, and transactions

#### Available Endpoints:
- `/vms/main` - Main vendor dashboard with balances and summary
- `/vms/po_view/<id>` - Purchase order details
- `/vms/stock/*` - Stock information (standard, return, in-house)
- `/vms/shipping/*` - Shipping information (standard, in-house)
- `/vms/transactions/*` - Transaction data (standard, in-house)
- `/vms/outstanding/*` - Outstanding balances and clearances
- `/vms/payments` - Payment history
- `/vms/bills` - Bill and refund information
- `/vms/blanket_order/<id>/attachment` - File attachment for blanket orders

### 3. Automation Features
- **In-House Clearance**: Automatic journal entry creation for vendor clearance
- **PO Bill Creation**: Automatic vendor bill generation when orders are closed
- **Configurable Settings**: Enable/disable automation features through settings

### 4. Enhanced Views
- **Partner Forms**: VMS integration fields and balance display
- **Sale Order Forms**: VMS status and action buttons
- **Configuration Settings**: VMS-specific configuration options

## Installation

1. **Install the Module**:
   ```bash
   # Copy the module to your addons directory
   cp -r mataa_vms_integration /path/to/odoo/addons/
   
   # Update the addons list in Odoo
   # Go to Apps > Update Apps List
   ```

2. **Install Dependencies**:
   - Ensure `mataa_base` module is installed
   - Ensure `mataa_order_management` module is installed
   - Ensure `mataa_product_management` module is installed

3. **Configure VMS Settings**:
   - Go to Settings > General Settings
   - Configure VMS settings:
     - Vendor Clearance Journal
     - Enable/disable VMS API
     - Enable/disable auto clearance
     - Enable/disable auto bill creation

## Configuration

### 1. Vendor Setup
1. **Create Standard Vendor**:
   - Go to Contacts > Create Contact
   - Set "Is VMS Vendor" to True
   - Set "Vendor Type" to "Standard Vendor"
   - Save the contact

2. **Create In-House Vendor**:
   - Go to Contacts > Create Contact
   - Set "Is VMS Vendor" to True
   - Set "Vendor Type" to "In-House Vendor"
   - Link to Standard Vendor Partner
   - Save the contact

### 2. Journal Configuration
1. **Create Clearance Journal**:
   - Go to Accounting > Configuration > Journals
   - Create a new General Journal for vendor clearance
   - Configure the journal settings

2. **Set Clearance Journal**:
   - Go to Settings > General Settings
   - Set "Vendor Clearance Journal" to the created journal

### 3. API Configuration
1. **Enable VMS API**:
   - Go to Settings > General Settings
   - Enable "Enable VMS API"

2. **Configure Authentication**:
   - Ensure JWT authentication is properly configured
   - Set up user accounts for vendors

## Usage

### 1. Vendor Portal Access
Vendors can access the VMS system through:
- **API Endpoints**: Direct API calls with authentication
- **Web Interface**: Odoo web interface for vendor users

### 2. API Authentication
```bash
# Login to get JWT token
curl -X POST http://your-odoo-instance/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "vendor_user", "password": "vendor_password"}'

# Use token for VMS API calls
curl -X GET http://your-odoo-instance/vms/main \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. Vendor Data Access
- **Balances**: Real-time financial balances across linked accounts
- **Stock Information**: Current stock levels and movements
- **Transaction History**: Complete transaction records
- **Shipping Status**: Real-time shipping information

## Technical Details

### 1. Models Extended
- `res.partner`: VMS vendor fields and relationships
- `sale.order`: VMS automation and tracking
- `purchase.order`: VMS integration fields
- `res.config.settings`: VMS configuration options

### 2. Controllers
- `VMSController`: Main API controller with all VMS endpoints
- Authentication middleware integration
- Error handling and logging

### 3. Security
- Role-based access control
- API authentication required
- Vendor data isolation

## API Reference

### Authentication
All VMS endpoints require JWT authentication via the `Authorization` header:
```
Authorization: Bearer <jwt_token>
```

### Response Format
All API responses follow the standard Mataa API response format:
```json
{
  "status": "success|error",
  "data": {...},
  "message": "Optional message",
  "meta": {...}
}
```

### Error Handling
- **401 Unauthorized**: Invalid or missing authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **422 Validation Error**: Invalid request data
- **500 Internal Server Error**: Server-side error

## Troubleshooting

### Common Issues

1. **Module Not Installing**:
   - Check all dependencies are installed
   - Verify module structure and files
   - Check Odoo logs for errors

2. **API Authentication Failing**:
   - Verify JWT configuration
   - Check user permissions
   - Ensure vendor is properly configured

3. **Automation Not Working**:
   - Check VMS settings configuration
   - Verify journal configuration
   - Check automation flags are enabled

### Logs
VMS operations are logged with the logger name `mataa_vms_integration`. Check Odoo logs for detailed error information.

## Development

### Adding New Endpoints
1. Add new method to `VMSController`
2. Add route decorator with proper authentication
3. Implement business logic
4. Add proper error handling
5. Update documentation

### Extending Models
1. Inherit existing models in new files
2. Add VMS-specific fields and methods
3. Update security access rules
4. Test thoroughly

## Support

For technical support or questions:
- Check the Odoo logs for error details
- Review the configuration settings
- Ensure all dependencies are properly installed
- Contact the development team for complex issues

## Version History

- **v1.0**: Initial release with core VMS functionality
  - Unified vendor model
  - Complete API endpoint set
  - Automation features
  - Enhanced views and configuration 