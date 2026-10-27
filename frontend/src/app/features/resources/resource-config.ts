export type FieldType = 'text' | 'textarea' | 'date' | 'number' | 'select';

export interface ColumnConfig {
  key: string;
  label: string;
  type?: 'text' | 'status' | 'date' | 'money' | 'number';
  width?: string;
}

export interface FormFieldConfig {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  options?: Array<{ value: string; label: string }>;
}

export interface ResourcePageConfig {
  title: string;
  eyebrow: string;
  description: string;
  endpoint: string;
  icon: string;
  columns: ColumnConfig[];
  createFields?: FormFieldConfig[];
  canCreate?: boolean;
  searchPlaceholder?: string;
  emptyText?: string;
}

const STATUS = (values: string[]) => values.map((value) => ({
  value,
  label: value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
}));

export const RESOURCE_PAGES: Record<string, ResourcePageConfig> = {
  documents: {
    title: 'Documents',
    eyebrow: 'Project controls',
    description: 'Controlled documents, revisions and approval status across the project.',
    endpoint: 'documents/',
    icon: '▤',
    searchPlaceholder: 'Search document titles…',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'document_type', label: 'Type' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'confidentiality', label: 'Access', type: 'status' },
      { key: 'updated_at', label: 'Updated', type: 'date' },
    ],
    canCreate: true,
    createFields: [
      { key: 'title', label: 'Title', type: 'text', required: true },
      { key: 'document_type', label: 'Document type', type: 'text', placeholder: 'Drawing, contract, report…' },
      {
        key: 'confidentiality',
        label: 'Confidentiality',
        type: 'select',
        options: STATUS(['standard', 'confidential', 'restricted']),
      },
    ],
  },
  drawings: {
    title: 'Drawings',
    eyebrow: 'Design control',
    description: 'Drawing register with revisions, review status and issue history.',
    endpoint: 'drawings/',
    icon: '⌗',
    searchPlaceholder: 'Search drawing number or title…',
    columns: [
      { key: 'number', label: 'Number' },
      { key: 'title', label: 'Title' },
      { key: 'discipline', label: 'Discipline' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'updated_at', label: 'Updated', type: 'date' },
    ],
    canCreate: true,
    createFields: [
      { key: 'number', label: 'Drawing number', type: 'text', required: true, placeholder: 'A-101' },
      { key: 'title', label: 'Title', type: 'text', required: true },
      { key: 'discipline', label: 'Discipline', type: 'text', placeholder: 'Architectural' },
    ],
  },
  field: {
    title: 'Field operations',
    eyebrow: 'Site diary',
    description: 'Daily reports, weather, labour, equipment and site observations.',
    endpoint: 'daily-logs/',
    icon: '☼',
    searchPlaceholder: 'Search daily reports…',
    columns: [
      { key: 'log_date', label: 'Date', type: 'date' },
      { key: 'weather_summary', label: 'Weather' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'work_activities', label: 'Work activities' },
      { key: 'created_at', label: 'Created', type: 'date' },
    ],
    canCreate: true,
    createFields: [
      { key: 'log_date', label: 'Log date', type: 'date', required: true },
      { key: 'weather_summary', label: 'Weather summary', type: 'text' },
      { key: 'work_activities', label: 'Work activities', type: 'textarea' },
      { key: 'safety_notes', label: 'Safety notes', type: 'textarea' },
    ],
  },
  tasks: {
    title: 'Tasks',
    eyebrow: 'Delivery',
    description: 'Work items, priorities and due dates across the project team.',
    endpoint: 'tasks/',
    icon: '✓',
    searchPlaceholder: 'Search tasks…',
    columns: [
      { key: 'title', label: 'Task' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'priority', label: 'Priority', type: 'status' },
      { key: 'due_date', label: 'Due', type: 'date' },
      { key: 'progress_percent', label: 'Progress', type: 'number' },
    ],
    canCreate: true,
    createFields: [
      { key: 'title', label: 'Title', type: 'text', required: true },
      { key: 'description', label: 'Description', type: 'textarea' },
      {
        key: 'priority',
        label: 'Priority',
        type: 'select',
        options: STATUS(['low', 'medium', 'high', 'critical']),
      },
      { key: 'due_date', label: 'Due date', type: 'date' },
    ],
  },
  rfis: {
    title: 'RFIs & submittals',
    eyebrow: 'Information control',
    description: 'Requests for information, official responses and due-date tracking.',
    endpoint: 'rfis/',
    icon: '?',
    searchPlaceholder: 'Search RFI subject or number…',
    columns: [
      { key: 'number', label: 'Number' },
      { key: 'subject', label: 'Subject' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'priority', label: 'Priority', type: 'status' },
      { key: 'due_date', label: 'Due', type: 'date' },
    ],
    canCreate: true,
    createFields: [
      { key: 'number', label: 'RFI number', type: 'text', required: true, placeholder: 'RFI-021' },
      { key: 'subject', label: 'Subject', type: 'text', required: true },
      { key: 'question', label: 'Question', type: 'textarea', required: true },
      {
        key: 'priority',
        label: 'Priority',
        type: 'select',
        options: STATUS(['low', 'medium', 'high', 'critical']),
      },
      { key: 'due_date', label: 'Response due', type: 'date' },
    ],
  },
  financials: {
    title: 'Financials',
    eyebrow: 'Commercial',
    description: 'Change orders, cost impact and approval movement across the project.',
    endpoint: 'change-orders/',
    icon: '$',
    searchPlaceholder: 'Search change orders…',
    columns: [
      { key: 'number', label: 'Number' },
      { key: 'title', label: 'Title' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'amount', label: 'Amount', type: 'money' },
      { key: 'submitted_date', label: 'Submitted', type: 'date' },
    ],
    canCreate: true,
    createFields: [
      { key: 'number', label: 'Change order number', type: 'text', required: true, placeholder: 'CO-014' },
      { key: 'title', label: 'Title', type: 'text', required: true },
      { key: 'description', label: 'Description', type: 'textarea' },
      { key: 'amount', label: 'Amount', type: 'number', required: true },
      { key: 'reason', label: 'Reason', type: 'text', placeholder: 'Owner directive' },
      { key: 'submitted_date', label: 'Submitted date', type: 'date' },
    ],
  },
  quality: {
    title: 'Quality & safety',
    eyebrow: 'Assurance',
    description: 'Inspections, defects, punch lists and safety observations.',
    endpoint: 'inspections/',
    icon: '◎',
    searchPlaceholder: 'Search inspections…',
    columns: [
      { key: 'number', label: 'Number' },
      { key: 'title', label: 'Inspection' },
      { key: 'inspection_type', label: 'Type', type: 'status' },
      { key: 'status', label: 'Status', type: 'status' },
      { key: 'scheduled_date', label: 'Scheduled', type: 'date' },
    ],
    canCreate: true,
    createFields: [
      { key: 'number', label: 'Inspection number', type: 'text', required: true, placeholder: 'INS-042' },
      { key: 'title', label: 'Title', type: 'text', required: true },
      {
        key: 'inspection_type',
        label: 'Type',
        type: 'select',
        options: STATUS(['quality', 'safety', 'environmental', 'handover', 'other']),
      },
      { key: 'scheduled_date', label: 'Scheduled date', type: 'date' },
      { key: 'location', label: 'Location', type: 'text' },
    ],
  },
  reports: {
    title: 'Reports & analytics',
    eyebrow: 'Insight',
    description: 'Saved report definitions available to the organization.',
    endpoint: 'report-definitions/',
    icon: '◔',
    searchPlaceholder: 'Search reports…',
    columns: [
      { key: 'name', label: 'Report' },
      { key: 'report_type', label: 'Type', type: 'status' },
      { key: 'visibility', label: 'Visibility', type: 'status' },
      { key: 'created_at', label: 'Created', type: 'date' },
    ],
    canCreate: false,
  },
  integrations: {
    title: 'Integrations',
    eyebrow: 'Platform',
    description: 'API credentials and webhook subscriptions for external systems.',
    endpoint: 'api-applications/',
    icon: '⇄',
    searchPlaceholder: 'Search applications…',
    columns: [
      { key: 'name', label: 'Application' },
      { key: 'client_id', label: 'Client ID' },
      { key: 'is_active', label: 'Active' },
      { key: 'created_at', label: 'Created', type: 'date' },
    ],
    canCreate: false,
  },
};
