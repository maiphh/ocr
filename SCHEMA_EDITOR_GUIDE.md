# Schema Editor Guide

## Overview

The Schema Editor is now integrated into the sidebar for easy access while processing documents.

## Features

### 🎯 Two Edit Modes

#### 1. 📋 Field Editor (Visual Mode)
- User-friendly interface for managing fields
- Add, view, and delete fields with buttons
- Quick overview of field properties
- Perfect for non-technical users

#### 2. 💻 JSON Editor (Advanced Mode)
- Direct JSON editing with syntax highlighting
- Full control over schema structure
- Instant validation and error feedback
- Perfect for bulk edits and advanced users

## Using Field Editor Mode

### Adding a New Field
1. Click "➕ Add New Field"
2. Fill in the form:
   - **Field Name**: e.g., "Địa chỉ", "Phone Number"
   - **Type**: string, date, number, or boolean
   - **Required**: Check if field must exist
   - **Nullable**: Check if field can be empty
   - **Format**: For date fields (e.g., "iso-date")
   - **Description**: Explain what to extract
3. Click "✅ Add"

### Viewing Fields
- All fields listed in expandable sections
- Shows type, required status, and description
- Quick visual scan of current schema

### Deleting a Field
1. Expand the field you want to delete
2. Click "🗑️ Delete"
3. Field removed immediately

## Using JSON Editor Mode

### Editing Schema as JSON

```json
{
  "Field Name": {
    "type": "string",
    "required": true,
    "nullable": false,
    "description": "What this field represents"
  },
  "Another Field": {
    "type": "date",
    "required": false,
    "nullable": true,
    "format": "iso-date",
    "description": "Date field example"
  }
}
```

### JSON Editor Workflow
1. Switch to "💻 JSON Editor" mode
2. Edit the JSON directly in the text area
3. Click "✅ Apply JSON" to save changes
4. If there's an error, fix it and try again
5. Click "🔄 Reload" to discard changes

### Benefits of JSON Editor
- Copy/paste entire schemas
- Bulk edit multiple fields at once
- Advanced users can work faster
- Easy to duplicate and modify fields

## Common Actions

### Export Schema
- Click "💾 Export" button
- Downloads current schema as `schema.json`
- Save for backup or sharing

### Import Schema
1. Click "📥 Import Schema" section
2. Upload a `.json` file
3. Click "✅ Apply Imported Schema"
4. Schema loaded and applied

### Reset to Default
- Click "🔄 Reset" button
- Restores original BHXH schema
- All custom changes are lost

## Tips & Best Practices

### When to Use Field Editor
- Adding one or two fields
- Quick deletions
- Reviewing current schema
- First-time users

### When to Use JSON Editor
- Bulk adding/editing multiple fields
- Copying schema from documentation
- Complex nested structures
- Advanced users who prefer code

### Workflow Recommendations

**For New Document Types:**
1. Start with Field Editor to understand structure
2. Add/remove fields as needed
3. Export the schema
4. Reuse for similar documents

**For Quick Edits:**
1. Switch to JSON Editor
2. Make direct changes
3. Apply and test

**For Schema Sharing:**
1. Export your schema as JSON
2. Share the file with team members
3. They import it with one click

## Field Types

### String
```json
{
  "type": "string",
  "required": true,
  "description": "Text field"
}
```
Use for: Names, IDs, addresses, descriptions

### Date
```json
{
  "type": "date",
  "required": true,
  "format": "iso-date",
  "description": "Date in DD/MM/YYYY format"
}
```
Use for: Birth dates, start/end dates, timestamps

### Number
```json
{
  "type": "number",
  "required": true,
  "description": "Numeric value"
}
```
Use for: Counts, totals, amounts, scores

### Boolean
```json
{
  "type": "boolean",
  "required": false,
  "description": "Yes/No field"
}
```
Use for: Flags, checkboxes, yes/no questions

## Schema Statistics

At the bottom of the sidebar, you'll see:
- 📊 **Total Fields**: Number of fields in schema
- ✅ **Required**: Count of required fields
- ⭕ **Optional**: Count of optional fields

## Troubleshooting

### JSON Editor Errors

**"Invalid JSON" error:**
- Check for missing commas, brackets, or quotes
- Use a JSON validator online if needed
- Click "🔄 Reload" to start fresh

**"Schema must be a JSON object" error:**
- Schema must start with `{` and end with `}`
- Cannot be an array `[]` or string

### Changes Not Applying

- Click "✅ Apply JSON" or "✅ Add" button
- Watch for success/error messages
- Pipeline automatically reinitializes on schema changes

### Lost Changes

- Export your schema regularly
- Keep backup JSON files
- Use "🔄 Reset" only when you want to start over

## Keyboard Shortcuts in JSON Editor

- **Ctrl/Cmd + A**: Select all
- **Ctrl/Cmd + C**: Copy
- **Ctrl/Cmd + V**: Paste
- **Ctrl/Cmd + Z**: Undo
- **Tab**: Indent (if supported by browser)

## Examples

### Minimal Schema (2 fields)
```json
{
  "Name": {
    "type": "string",
    "required": true,
    "description": "Person's full name"
  },
  "Date": {
    "type": "date",
    "required": true,
    "format": "iso-date",
    "description": "Document date"
  }
}
```

### Complex Schema (Multiple fields)
```json
{
  "Patient Name": {
    "type": "string",
    "required": true,
    "description": "Full name of patient"
  },
  "Date of Birth": {
    "type": "date",
    "required": true,
    "format": "iso-date",
    "description": "DOB in DD/MM/YYYY"
  },
  "Patient ID": {
    "type": "string",
    "required": true,
    "description": "Unique patient identifier"
  },
  "Visit Date": {
    "type": "date",
    "required": false,
    "nullable": true,
    "format": "iso-date",
    "description": "Date of visit"
  },
  "Total Days": {
    "type": "number",
    "required": false,
    "nullable": true,
    "description": "Total treatment days"
  }
}
```

## Integration with Document Processing

1. **Before Processing**: Set up your schema
2. **During Processing**: Schema is used to extract fields
3. **After Processing**: Results match your schema exactly
4. **Schema Changes**: Apply anytime, next processing uses new schema

The sidebar schema editor is always accessible, allowing you to adjust your extraction strategy on the fly!
