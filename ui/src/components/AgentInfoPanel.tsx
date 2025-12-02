import { useState, useRef, useEffect } from 'react';

interface AgentInfoPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  agentId: string;
}

// Mock customer data
const MOCK_CUSTOMERS = [
  {
    id: 'cust_test',
    name: 'Francesco Ciannella',
    dob: '1990-01-01',
    ssn_last4: '6001',
    secret_question: 'What is your favorite color?',
    secret_answer: 'blue',
    phone: '***-***-1234',
    accounts: [
      { id: 'WT-CHK-001', nickname: 'Everyday Chequing', number: '6001', currency: 'USD', balance: 5200.50, wire_enabled: true, daily_limit: 10000 },
      { id: 'WT-SAV-001', nickname: 'High Interest Savings', number: '7182', currency: 'USD', balance: 12000.00, wire_enabled: false, daily_limit: 0 },
    ],
  },
  {
    id: 'cust_alice',
    name: 'Alice Stone',
    dob: '1985-05-12',
    ssn_last4: '1101',
    secret_question: 'Favorite color?',
    secret_answer: 'green',
    phone: '***-***-2211',
    accounts: [
      { id: 'WT-CHK-101', nickname: 'Everyday Chequing', number: '1101', currency: 'CAD', balance: 2450.00, wire_enabled: true, daily_limit: 7500 },
      { id: 'WT-SAV-101', nickname: 'High Interest Savings', number: '7101', currency: 'CAD', balance: 8000.00, wire_enabled: false, daily_limit: 0 },
    ],
  },
  {
    id: 'cust_bob',
    name: 'Bob Rivera',
    dob: '1978-11-30',
    ssn_last4: '1202',
    secret_question: 'Favorite color?',
    secret_answer: 'red',
    phone: '***-***-3322',
    accounts: [
      { id: 'WT-CHK-202', nickname: 'Primary Chequing', number: '1202', currency: 'USD', balance: 3900.00, wire_enabled: true, daily_limit: 5000 },
    ],
  },
  {
    id: 'cust_carla',
    name: 'Carla Nguyen',
    dob: '1992-03-14',
    ssn_last4: '7303',
    secret_question: 'Favorite color?',
    secret_answer: 'blue',
    phone: '***-***-4433',
    accounts: [
      { id: 'WT-SAV-303', nickname: 'Savings', number: '7303', currency: 'EUR', balance: 1500.00, wire_enabled: true, daily_limit: 3000 },
    ],
  },
  {
    id: 'cust_dave',
    name: 'David Patel',
    dob: '1989-07-21',
    ssn_last4: '1404',
    secret_question: 'Favorite animal?',
    secret_answer: 'tiger',
    phone: '***-***-5544',
    accounts: [
      { id: 'WT-CHK-404', nickname: 'Everyday Chequing', number: '1404', currency: 'USD', balance: 15000.00, wire_enabled: true, daily_limit: 20000 },
    ],
  },
  {
    id: 'cust_eve',
    name: 'Evelyn Moore',
    dob: '1995-09-09',
    ssn_last4: '7505',
    secret_question: 'Favorite season?',
    secret_answer: 'summer',
    phone: '***-***-6655',
    accounts: [
      { id: 'WT-SAV-505', nickname: 'High Interest Savings', number: '7505', currency: 'CAD', balance: 6400.00, wire_enabled: true, daily_limit: 4000 },
    ],
  },
];

// Mock telco customers
const MOCK_TELCO_CUSTOMERS = [
  {
    id: 'telco_alex',
    name: 'Alex Lee',
    dob: '1988-05-22',
    email: 'alex.lee@example.com',
    msisdn: '+15551234567',
    package_id: 'P-40',
    package_name: 'Standard 40GB 5G',
    monthly_fee: 40.0,
    data_gb: 40,
    data_gb_used: 12.5,
    data_gb_remaining: 27.5,
    minutes: 1000,
    sms: 1000,
    fiveg: true,
    contract_status: 'active',
    contract_start: '2024-01-10',
    contract_end: '2026-01-10',
    early_termination_fee: 150.0,
    auto_renew: true,
    billing_cycle_day: 5,
    last_bill_amount: 45.0,
    otp: '246810',
  },
  {
    id: 'telco_sam',
    name: 'Sam Taylor',
    dob: '1992-03-14',
    email: 'sam.taylor@example.co.uk',
    msisdn: '+447911123456',
    package_id: 'P-10',
    package_name: 'Lite 10GB 4G',
    monthly_fee: 25.0,
    data_gb: 10,
    data_gb_used: 8.1,
    data_gb_remaining: 1.9,
    minutes: 500,
    sms: 500,
    fiveg: false,
    contract_status: 'active',
    contract_start: '2024-06-01',
    contract_end: '2025-12-01',
    early_termination_fee: 80.0,
    auto_renew: false,
    billing_cycle_day: 12,
    last_bill_amount: 29.0,
    otp: '135790',
  },
];

// Mock fees customers
const MOCK_FEES_CUSTOMERS = [
  {
    id: 'fees_francesco',
    name: 'Francesco Ciannella',
    dob: '1990-01-01',
    secret_question: 'What is your favorite color?',
    secret_answer: 'blue',
    accounts: [
      { 
        id: 'A-CHK-001', 
        nickname: 'Everyday Chequing', 
        number: '6001', 
        product_type: 'CHK',
        current_package: 'None',
        total_fees_90days: 52.50,
        recent_fees: [
          { date: '2025-09-01', amount: 10.00, description: 'Monthly maintenance', fee_code: 'MAINTENANCE' },
          { date: '2025-08-20', amount: 12.50, description: 'NSF fee', fee_code: 'NSF' },
          { date: '2025-08-01', amount: 10.00, description: 'Monthly maintenance', fee_code: 'MAINTENANCE' },
          { date: '2025-07-01', amount: 10.00, description: 'Monthly maintenance', fee_code: 'MAINTENANCE' },
          { date: '2025-06-01', amount: 10.00, description: 'Monthly maintenance', fee_code: 'MAINTENANCE' },
        ]
      },
      { 
        id: 'A-SAV-001', 
        nickname: 'High Interest Savings', 
        number: '7182', 
        product_type: 'SAV',
        current_package: 'None',
        total_fees_90days: 11.00,
        recent_fees: [
          { date: '2025-08-10', amount: 3.00, description: 'ATM withdrawal fee', fee_code: 'ATM' },
          { date: '2025-07-05', amount: 3.00, description: 'ATM withdrawal fee', fee_code: 'ATM' },
          { date: '2025-06-20', amount: 5.00, description: 'Excess withdrawal', fee_code: 'EXCESS_WITHDRAWAL' },
        ]
      },
    ],
    total_fees_all_accounts: 63.50,
    recommended_package: 'Chequing Plus',
    potential_savings: 37.50,
  },
  {
    id: 'fees_alice',
    name: 'Alice Stone',
    dob: '1985-05-12',
    secret_question: 'Favorite color?',
    secret_answer: 'green',
    accounts: [
      { 
        id: 'A-CHK-101', 
        nickname: 'Everyday Chequing', 
        number: '1101', 
        product_type: 'CHK',
        current_package: 'None',
        total_fees_90days: 25.25,
        recent_fees: [
          { date: '2025-08-03', amount: 10.00, description: 'Monthly maintenance', fee_code: 'MAINTENANCE' },
          { date: '2025-07-02', amount: 10.00, description: 'Monthly maintenance', fee_code: 'MAINTENANCE' },
          { date: '2025-06-14', amount: 12.50, description: 'NSF fee', fee_code: 'NSF' },
          { date: '2025-05-19', amount: 2.75, description: 'Foreign exchange fee', fee_code: 'FX_FEE' },
        ]
      },
      { 
        id: 'A-SAV-101', 
        nickname: 'High Interest Savings', 
        number: '7101', 
        product_type: 'SAV',
        current_package: 'None',
        total_fees_90days: 8.00,
        recent_fees: [
          { date: '2025-07-22', amount: 3.00, description: 'ATM withdrawal fee', fee_code: 'ATM' },
          { date: '2025-05-10', amount: 5.00, description: 'Excess withdrawal', fee_code: 'EXCESS_WITHDRAWAL' },
        ]
      },
    ],
    total_fees_all_accounts: 33.25,
    recommended_package: 'Chequing Plus',
    potential_savings: 18.25,
  },
];

// Mock healthcare patients
const MOCK_HEALTHCARE_PATIENTS = [
  {
    id: 'pt_jmarshall',
    name: 'John Marshall',
    dob: '1960-01-01',
    mrn: 'JM-1960-0001',
    mrn_last4: '0001',
    secret_question: 'What is your favorite color?',
    secret_answer: 'blue',
    phone: '+1-555-0101',
    email: 'john.marshall@example.com',
    address: '12 Park Ave, Santa Clara, CA 95050',
    allergies: ['Penicillin'],
    medications: [
      { name: 'Acetaminophen', sig: '500 mg, every 6 hours as needed for pain', otc: true }
    ],
    conditions: ['Hypertension'],
    recent_visits: [
      { date: '2025-08-15', type: 'Primary Care', reason: 'Annual wellness visit', outcome: 'Continue current meds' }
    ],
    vitals: {
      date: '2025-08-15',
      bp: '128/78',
      hr: 72,
      temp_f: 98.4,
      bmi: 26.1
    },
    preferred_pharmacy: 'CVS Pharmacy - 1010 El Camino Real, Santa Clara, CA'
  },
  {
    id: 'pt_fciannella',
    name: 'Francesco Ciannella',
    dob: '1990-01-01',
    mrn: 'FC-1990-6001',
    mrn_last4: '6001',
    secret_question: 'What city were you born in?',
    secret_answer: 'rome',
    phone: '+1-555-0202',
    email: 'francesco@example.com',
    address: '101 State St, San Jose, CA 95110',
    allergies: ['NKA (No Known Allergies)'],
    medications: [
      { name: 'Lisinopril', sig: '10 mg, once daily', otc: false }
    ],
    conditions: ['Hypertension'],
    recent_visits: [
      { date: '2025-07-02', type: 'Urgent Care', reason: 'Sore throat', outcome: 'Viral pharyngitis; supportive care' }
    ],
    vitals: {
      date: '2025-07-02',
      bp: '122/76',
      hr: 68,
      temp_f: 98.2,
      bmi: 24.9
    },
    preferred_pharmacy: 'CVS Pharmacy - 1010 El Camino Real, Santa Clara, CA'
  },
];

const DEFAULT_OTP = '123456';

export function AgentInfoPanel({ isOpen, onToggle, agentId }: AgentInfoPanelProps) {
  // Determine which customer list to use based on agent type
  const customers = 
    agentId === 'telco_agent' ? MOCK_TELCO_CUSTOMERS :
    agentId === 'rbc_fees_agent' ? MOCK_FEES_CUSTOMERS :
    agentId === 'healthcare_agent' ? MOCK_HEALTHCARE_PATIENTS :
    MOCK_CUSTOMERS;
  
  const [panelWidth, setPanelWidth] = useState(320); // Default 320px
  const [isResizing, setIsResizing] = useState(false);
  const [activeTab, setActiveTab] = useState<'info' | 'users'>('info');
  const [selectedCustomerId, setSelectedCustomerId] = useState(customers[0].id);
  const panelRef = useRef<HTMLDivElement>(null);
  
  const minWidth = 280; // Minimum panel width
  const maxWidth = 600; // Maximum panel width
  
  const selectedCustomer: any = customers.find(c => c.id === selectedCustomerId) || customers[0];
  
  // Handle mouse move during resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !panelRef.current) return;
      
      const rect = panelRef.current.getBoundingClientRect();
      const newWidth = rect.right - e.clientX;
      
      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setPanelWidth(newWidth);
      }
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
    };
    
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);
  
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };
  // Agent-specific information
  const agentInfo = {
    wire_transfer_agent: {
      name: 'Wire Transfer Agent',
      icon: '💳',
      description: 'Specialized banking assistant that helps customers initiate domestic and international wire transfers with full compliance and security.',
      capabilities: [
        'Customer identity verification',
        'Domestic wire transfers (US)',
        'International wire transfers',
        'Foreign exchange (FX) rate quotes',
        'Wire fee calculation',
        'Transfer limit verification',
        'Beneficiary validation',
        'OTP-based authorization',
        'Real-time transfer quotes',
      ],
      languages: ['English (en-US)'],
      securityFeatures: [
        'Multi-factor authentication',
        'Identity verification (DOB + SSN/Secret)',
        'One-Time Password (OTP)',
        'Transaction limits enforcement',
      ],
    },
    claims_investigation_agent: {
      name: 'Claims Investigation Agent',
      icon: '🔍',
      description: 'AI-powered investigation agent that makes outbound phone calls to customers for insurance claim verification, fraud detection, and follow-ups.',
      capabilities: [
        'Initiate outbound customer calls',
        'Retrieve call transcripts & summaries',
        'Track call history and status',
        'Analyze call outcomes',
        'Fraud verification calls',
        'Claim verification outreach',
        'Missing information follow-ups',
        'Automated batch calling',
        'Real-time call status tracking',
      ],
      languages: ['English (en-US)', 'Multi-language support'],
      securityFeatures: [
        'Twilio verified calling',
        'Call recording and audit trail',
        'Outcome tracking',
        'Secure call metadata storage',
      ],
    },
    telco_agent: {
      name: 'Telco Agent',
      icon: '📱',
      description: 'Mobile operator assistant that helps customers with plan management, roaming, data usage, and package recommendations with SMS OTP verification.',
      capabilities: [
        'SMS OTP verification',
        'Current plan and contract status',
        'Data balance and usage tracking',
        'Roaming rates and passes',
        'Package recommendations',
        'Plan changes (immediate or next cycle)',
        'Addon management',
        'Contract closure with fee calculation',
        'Billing summary and alerts',
      ],
      languages: ['English (en-US)', 'Multi-language support'],
      securityFeatures: [
        'SMS-based OTP authentication',
        'Mobile number verification',
        'Account access control',
        'Secure transaction authorization',
      ],
    },
    rbc_fees_agent: {
      name: 'Banking Fees Agent',
      icon: '💰',
      description: 'Banking assistant that helps customers understand account fees, review transaction history, check refund eligibility, and recommend package upgrades to save on fees.',
      capabilities: [
        'Identity verification (DOB + secret answer)',
        'Fee history review and analysis',
        'Fee explanation and categorization',
        'Refund eligibility checking',
        'Account upgrade recommendations',
        'Fee trend analysis',
        'Package comparison',
        'Cost-benefit analysis',
        'Proactive fee prevention tips',
      ],
      languages: ['English (en-US)', 'Multi-language support'],
      securityFeatures: [
        'Multi-factor identity verification',
        'DOB and secret question authentication',
        'Account number verification',
        'Secure transaction history access',
      ],
    },
    healthcare_agent: {
      name: 'Healthcare Telehealth Nurse',
      icon: '🏥',
      description: '24/7 AI telehealth nurse for existing patients. Authenticates callers, retrieves patient profiles, performs symptom triage, provides medical advice, and books appointments.',
      capabilities: [
        'Patient authentication (DOB + MRN/secret)',
        'Medical record retrieval',
        'Allergy and medication checking',
        'Symptom recognition and triage',
        'Red flag identification',
        'Self-care guidance',
        'Urgent case escalation',
        'Appointment scheduling',
        'Pharmacy confirmation',
        'Call logging and documentation',
      ],
      languages: ['English (en-US)', 'Multi-language support'],
      securityFeatures: [
        'Multi-step patient verification',
        'DOB and MRN authentication',
        'Secret question validation',
        'HIPAA-compliant data handling',
      ],
    },
  };

  const agent = agentInfo[agentId as keyof typeof agentInfo];

  if (!agent) {
    return null;
  }

  return (
    <>
      {/* Vertical Toggle Bar - Full Height */}
      <button
        onClick={onToggle}
        className={`flex-shrink-0 flex items-center justify-center bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 ${
          isOpen ? 'w-0 opacity-0' : 'w-3.5 opacity-100'
        }`}
        aria-label="Show agent info"
        title="Show agent info"
        style={{ 
          minWidth: isOpen ? '0' : '14px',
          transition: 'all 0.3s ease-in-out'
        }}
      >
        {/* Left arrow (<) to open */}
        <svg className="w-3 h-3 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* Panel - Slides in from right with resize handle */}
      <aside
        ref={panelRef}
        className={`relative flex-shrink-0 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 overflow-hidden transition-all duration-300 ease-in-out group/panel ${
          isOpen ? 'opacity-100' : 'w-0 opacity-0'
        }`}
        style={{ 
          width: isOpen ? `${panelWidth}px` : '0',
          minWidth: isOpen ? `${minWidth}px` : '0'
        }}
      >
        {/* Resize Handle - Left edge (1px wide) */}
        {isOpen && (
          <div
            className="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-[#76B900] transition-colors z-20 group"
            onMouseDown={handleResizeStart}
          >
            {/* Visual indicator on hover */}
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-gray-300 dark:bg-gray-600 group-hover:bg-[#76B900] transition-colors" />
          </div>
        )}
        
        {/* Vertical Close Bar - Right edge (14px wide, appears on hover) */}
        {isOpen && (
          <button
            onClick={onToggle}
            className="absolute right-0 top-0 bottom-0 w-3.5 flex items-center justify-center bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 z-10 opacity-0 group-hover/panel:opacity-100"
            aria-label="Hide agent info"
            title="Hide agent info"
          >
            {/* Right arrow (>) to close */}
            <svg className="w-3 h-3 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}
        
        {/* Panel content with scroll - only offset by resize handle */}
        <div className="h-full flex flex-col overflow-hidden" style={{ marginLeft: isOpen ? '1px' : '0' }}>
          {/* Tabs Header */}
          <div className="flex-shrink-0 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
            <div className="flex">
              <button
                onClick={() => setActiveTab('info')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === 'info'
                    ? 'border-[#76B900] text-[#76B900]'
                    : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                Agent Info
              </button>
              <button
                onClick={() => setActiveTab('users')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === 'users'
                    ? 'border-[#76B900] text-[#76B900]'
                    : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                Test Users
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === 'info' && (
              <div className="p-6">
                {/* Header */}
                <div className="mb-6">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-4xl">{agent.icon}</span>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                      {agent.name}
                    </h2>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                    {agent.description}
                  </p>
                </div>

          {/* Capabilities */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Capabilities
            </h3>
            <ul className="space-y-2">
              {agent.capabilities.map((capability, index) => (
                <li key={index} className="text-xs text-gray-600 dark:text-gray-400 flex items-start gap-2">
                  <span className="text-[#76B900] mt-0.5">•</span>
                  <span>{capability}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Security Features */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              Security
            </h3>
            <ul className="space-y-2">
              {agent.securityFeatures.map((feature, index) => (
                <li key={index} className="text-xs text-gray-600 dark:text-gray-400 flex items-start gap-2">
                  <span className="text-[#76B900] mt-0.5">🔒</span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Languages */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
              </svg>
              Languages
            </h3>
            <ul className="space-y-1">
              {agent.languages.map((lang, index) => (
                <li key={index} className="text-xs text-gray-600 dark:text-gray-400">
                  {lang}
                </li>
              ))}
            </ul>
          </div>

                {/* Footer Note */}
                <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-xs text-gray-500 dark:text-gray-500 italic">
                    This agent uses mock data for development. All transactions are simulated.
                  </p>
                </div>
              </div>
            )}

            {activeTab === 'users' && (
              <div className="p-6">
                {/* User Selector */}
                <div className="mb-6">
                  <label className="block text-sm font-semibold text-gray-900 dark:text-white mb-2">
                    Select Test Customer
                  </label>
                  <select
                    value={selectedCustomerId}
                    onChange={(e) => setSelectedCustomerId(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:border-transparent"
                  >
                    {customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>
                        {customer.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Customer Profile */}
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                    <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    Profile
                  </h3>
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-600 dark:text-gray-400">Full Name:</span>
                      <span className="text-xs font-medium text-gray-900 dark:text-white">{selectedCustomer.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-600 dark:text-gray-400">Date of Birth:</span>
                      <span className="text-xs font-medium text-gray-900 dark:text-white">{selectedCustomer.dob}</span>
                    </div>
                    {agentId === 'telco_agent' ? (
                      <>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Email:</span>
                          <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).email}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Mobile:</span>
                          <span className="text-xs font-mono font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).msisdn}</span>
                        </div>
                      </>
                    ) : agentId === 'rbc_fees_agent' ? (
                      <>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Customer ID:</span>
                          <span className="text-xs font-mono font-medium text-gray-900 dark:text-white">{selectedCustomer.id}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Total Accounts:</span>
                          <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).accounts?.length || 0}</span>
                        </div>
                      </>
                    ) : agentId === 'healthcare_agent' ? (
                      <>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">MRN:</span>
                          <span className="text-xs font-mono font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).mrn}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Phone:</span>
                          <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).phone}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Email:</span>
                          <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).email}</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">SSN Last 4:</span>
                          <span className="text-xs font-mono font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).ssn_last4}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Phone:</span>
                          <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).phone}</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Security Info / SMS OTP / Fees Security */}
                {agentId === 'telco_agent' ? (
                  <div className="mb-6">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      SMS OTP Verification
                    </h3>
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-600 dark:text-gray-400">Mobile Number:</span>
                        <span className="text-xs font-mono font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).msisdn}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-600 dark:text-gray-400">SMS OTP Code:</span>
                        <span className="text-xs font-mono font-medium text-[#76B900]">{(selectedCustomer as any).otp}</span>
                      </div>
                      <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                        <p className="text-xs text-blue-800 dark:text-blue-400">Use this code when prompted for SMS verification</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mb-6">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      Security
                    </h3>
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-2">
                      <div>
                        <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">Secret Question:</span>
                        <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).secret_question}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-600 dark:text-gray-400">Answer:</span>
                        <span className="text-xs font-medium text-gray-900 dark:text-white">{(selectedCustomer as any).secret_answer}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-600 dark:text-gray-400">OTP Code:</span>
                        <span className="text-xs font-mono font-medium text-[#76B900]">{DEFAULT_OTP}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Accounts / Mobile Package */}
                {agentId === 'telco_agent' ? (
                  <>
                    {/* Mobile Package Info */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                        Mobile Package
                      </h3>
                      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-900 dark:text-white">{selectedCustomer.package_name}</span>
                          {selectedCustomer.fiveg ? (
                            <span className="text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 px-2 py-0.5 rounded-full font-semibold">
                              5G
                            </span>
                          ) : (
                            <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-400 px-2 py-0.5 rounded-full">
                              4G
                            </span>
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex justify-between">
                            <span className="text-xs text-gray-600 dark:text-gray-400">Monthly Fee:</span>
                            <span className="text-xs font-semibold text-gray-900 dark:text-white">${selectedCustomer.monthly_fee}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-gray-600 dark:text-gray-400">Data Allowance:</span>
                            <span className="text-xs text-gray-900 dark:text-white">{selectedCustomer.data_gb} GB</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-gray-600 dark:text-gray-400">Data Used:</span>
                            <span className="text-xs font-medium text-orange-600 dark:text-orange-400">{selectedCustomer.data_gb_used} GB</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-gray-600 dark:text-gray-400">Data Remaining:</span>
                            <span className="text-xs font-semibold text-[#76B900]">{selectedCustomer.data_gb_remaining} GB</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-gray-600 dark:text-gray-400">Minutes:</span>
                            <span className="text-xs text-gray-900 dark:text-white">{selectedCustomer.minutes}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-xs text-gray-600 dark:text-gray-400">SMS:</span>
                            <span className="text-xs text-gray-900 dark:text-white">{selectedCustomer.sms}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Contract Info */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Contract
                      </h3>
                      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-2">
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Status:</span>
                          <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full font-medium">
                            {selectedCustomer.contract_status}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Start Date:</span>
                          <span className="text-xs text-gray-900 dark:text-white">{selectedCustomer.contract_start}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">End Date:</span>
                          <span className="text-xs text-gray-900 dark:text-white">{selectedCustomer.contract_end}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Auto Renew:</span>
                          <span className="text-xs text-gray-900 dark:text-white">{selectedCustomer.auto_renew ? 'Yes' : 'No'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Termination Fee:</span>
                          <span className="text-xs font-semibold text-red-600 dark:text-red-400">${selectedCustomer.early_termination_fee}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Billing Cycle:</span>
                          <span className="text-xs text-gray-900 dark:text-white">Day {selectedCustomer.billing_cycle_day}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600 dark:text-gray-400">Last Bill:</span>
                          <span className="text-xs font-semibold text-gray-900 dark:text-white">${selectedCustomer.last_bill_amount}</span>
                        </div>
                      </div>
                    </div>
                  </>
                ) : agentId === 'healthcare_agent' ? (
                  <>
                    {/* Medical Alerts */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        Allergies & Alerts
                      </h3>
                      <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 border border-red-200 dark:border-red-800">
                        {selectedCustomer.allergies.map((allergy: any, idx: number) => (
                          <div key={idx} className="flex items-center gap-2 text-red-900 dark:text-red-300">
                            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                            <span className="text-sm font-semibold">{allergy}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Medications */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                        </svg>
                        Current Medications ({selectedCustomer.medications.length})
                      </h3>
                      <div className="space-y-2">
                        {selectedCustomer.medications.map((med: any, idx: number) => (
                          <div key={idx} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-semibold text-gray-900 dark:text-white">{med.name}</span>
                              {med.otc && (
                                <span className="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded-full">
                                  OTC
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-gray-600 dark:text-gray-400">{med.sig}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Conditions & Vitals */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                        </svg>
                        Medical Summary
                      </h3>
                      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-3">
                        <div>
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 block mb-1">Active Conditions:</span>
                          <div className="flex flex-wrap gap-1">
                            {selectedCustomer.conditions.map((condition: any, idx: number) => (
                              <span key={idx} className="text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 px-2 py-0.5 rounded-full">
                                {condition}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 block mb-2">Latest Vitals ({selectedCustomer.vitals.date}):</span>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">BP:</span>
                              <span className="text-xs font-medium text-gray-900 dark:text-white">{selectedCustomer.vitals.bp}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">HR:</span>
                              <span className="text-xs font-medium text-gray-900 dark:text-white">{selectedCustomer.vitals.hr} bpm</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Temp:</span>
                              <span className="text-xs font-medium text-gray-900 dark:text-white">{selectedCustomer.vitals.temp_f}°F</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">BMI:</span>
                              <span className="text-xs font-medium text-gray-900 dark:text-white">{selectedCustomer.vitals.bmi}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Recent Visits */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Recent Visits
                      </h3>
                      <div className="space-y-2">
                        {selectedCustomer.recent_visits.map((visit: any, idx: number) => (
                          <div key={idx} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-semibold text-gray-900 dark:text-white">{visit.type}</span>
                              <span className="text-xs text-gray-500 dark:text-gray-400">{visit.date}</span>
                            </div>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                              <span className="font-medium">Reason:</span> {visit.reason}
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400">
                              <span className="font-medium">Outcome:</span> {visit.outcome}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Preferred Pharmacy */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                        Preferred Pharmacy
                      </h3>
                      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <p className="text-xs text-gray-900 dark:text-white">{selectedCustomer.preferred_pharmacy}</p>
                      </div>
                    </div>
                  </>
                ) : agentId === 'rbc_fees_agent' ? (
                  <>
                    {/* Fee Summary */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                        Fee Summary (Last 90 Days)
                      </h3>
                      <div className="bg-gradient-to-br from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 rounded-lg p-4 border border-red-200 dark:border-red-800">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-semibold text-red-900 dark:text-red-300">Total Fees Charged</span>
                          <span className="text-lg font-bold text-red-600 dark:text-red-400">${selectedCustomer.total_fees_all_accounts.toFixed(2)}</span>
                        </div>
                        {selectedCustomer.recommended_package && (
                          <div className="mt-3 pt-3 border-t border-red-200 dark:border-red-700">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-red-800 dark:text-red-300">Potential Savings with {selectedCustomer.recommended_package}</span>
                              <span className="text-sm font-bold text-green-600 dark:text-green-400">${selectedCustomer.potential_savings.toFixed(2)}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Accounts with Fees */}
                    <div className="mb-6">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                        </svg>
                        Accounts & Fee History ({selectedCustomer.accounts.length})
                      </h3>
                      <div className="space-y-4">
                        {selectedCustomer.accounts.map((account: any) => (
                          <div key={account.id} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                            <div className="flex items-center justify-between mb-3">
                              <div>
                                <span className="text-xs font-semibold text-gray-900 dark:text-white block">
                                  {account.nickname}
                                </span>
                                <span className="text-xs text-gray-600 dark:text-gray-400">...{account.number}</span>
                              </div>
                              <span className="text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 px-2 py-1 rounded-full font-semibold">
                                ${account.total_fees_90days.toFixed(2)} in fees
                              </span>
                            </div>
                            
                            {account.current_package !== 'None' && (
                              <div className="mb-2 pb-2 border-b border-gray-200 dark:border-gray-700">
                                <div className="flex justify-between">
                                  <span className="text-xs text-gray-600 dark:text-gray-400">Current Package:</span>
                                  <span className="text-xs font-medium text-gray-900 dark:text-white">{account.current_package}</span>
                                </div>
                              </div>
                            )}

                            <div className="space-y-1.5">
                              <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Recent Fees:</h4>
                              {account.recent_fees.slice(0, 3).map((fee: any, idx: number) => (
                                <div key={idx} className="flex justify-between items-center py-1 px-2 bg-white dark:bg-gray-900 rounded">
                                  <div className="flex-1">
                                    <span className="text-xs text-gray-900 dark:text-white block">{fee.description}</span>
                                    <span className="text-xs text-gray-500 dark:text-gray-400">{fee.date}</span>
                                  </div>
                                  <span className="text-xs font-semibold text-red-600 dark:text-red-400">${fee.amount.toFixed(2)}</span>
                                </div>
                              ))}
                              {account.recent_fees.length > 3 && (
                                <div className="text-xs text-gray-500 dark:text-gray-400 italic text-center pt-1">
                                  + {account.recent_fees.length - 3} more fees
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="mb-6">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4 text-[#76B900]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                      </svg>
                      Accounts ({selectedCustomer.accounts.length})
                    </h3>
                    <div className="space-y-3">
                      {selectedCustomer.accounts.map((account: any) => (
                        <div key={account.id} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold text-gray-900 dark:text-white">
                              {account.nickname}
                            </span>
                            {account.wire_enabled ? (
                              <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full">
                                Wire Enabled
                              </span>
                            ) : (
                              <span className="text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 px-2 py-0.5 rounded-full">
                                Wire Disabled
                              </span>
                            )}
                          </div>
                          <div className="space-y-1">
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Account #:</span>
                              <span className="text-xs font-mono text-gray-900 dark:text-white">...{account.number}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-gray-600 dark:text-gray-400">Balance:</span>
                              <span className="text-xs font-semibold text-gray-900 dark:text-white">
                                {account.currency} ${account.balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </span>
                            </div>
                            {account.wire_enabled && (
                              <div className="flex justify-between">
                                <span className="text-xs text-gray-600 dark:text-gray-400">Daily Limit:</span>
                                <span className="text-xs text-gray-900 dark:text-white">
                                  ${account.daily_limit.toLocaleString('en-US')}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Quick Copy Reference */}
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-300 mb-2">
                    Quick Reference
                  </h3>
                  {agentId === 'telco_agent' ? (
                    <div className="text-xs text-blue-800 dark:text-blue-400 space-y-1 font-mono">
                      <p>Name: {selectedCustomer.name}</p>
                      <p>Mobile: {selectedCustomer.msisdn}</p>
                      <p>DOB: {selectedCustomer.dob}</p>
                      <p>OTP: {selectedCustomer.otp}</p>
                      <p>Package: {selectedCustomer.package_name}</p>
                      <p>Data: {selectedCustomer.data_gb_remaining}GB remaining</p>
                    </div>
                  ) : agentId === 'rbc_fees_agent' ? (
                    <div className="text-xs text-blue-800 dark:text-blue-400 space-y-1 font-mono">
                      <p>Name: {selectedCustomer.name}</p>
                      <p>DOB: {selectedCustomer.dob}</p>
                      <p>Answer: {selectedCustomer.secret_answer}</p>
                      <p>Total Fees: ${selectedCustomer.total_fees_all_accounts.toFixed(2)}</p>
                      <p>Savings: ${selectedCustomer.potential_savings.toFixed(2)}</p>
                      <p>Upgrade: {selectedCustomer.recommended_package}</p>
                    </div>
                  ) : agentId === 'healthcare_agent' ? (
                    <div className="text-xs text-blue-800 dark:text-blue-400 space-y-1 font-mono">
                      <p>Name: {selectedCustomer.name}</p>
                      <p>DOB: {selectedCustomer.dob}</p>
                      <p>MRN Last-4: {selectedCustomer.mrn_last4}</p>
                      <p>Answer: {selectedCustomer.secret_answer}</p>
                      <p>Allergies: {selectedCustomer.allergies.join(', ')}</p>
                      <p>Meds: {selectedCustomer.medications.length} active</p>
                    </div>
                  ) : (
                    <div className="text-xs text-blue-800 dark:text-blue-400 space-y-1 font-mono">
                      <p>Name: {selectedCustomer.name}</p>
                      <p>DOB: {selectedCustomer.dob}</p>
                      <p>SSN: {selectedCustomer.ssn_last4}</p>
                      <p>Answer: {selectedCustomer.secret_answer}</p>
                      <p>OTP: {DEFAULT_OTP}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
