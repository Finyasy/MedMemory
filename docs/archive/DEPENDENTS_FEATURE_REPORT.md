# MedMemory - Family & Dependents Feature

## Overview

Enable parents, guardians, and caretakers to manage health records for their children and dependents within MedMemory. Also provide comprehensive health profile management for all users.

**Vision**: *"One family, one medical memory. Track everyone's health in one place."*

---

## Complete Health Profile

After signing up, users should be able to complete their health profile with the following information. The same fields (where applicable) apply to dependents.

### Profile Categories

#### 1. Basic Information (Required)
| Field | Type | Description |
|-------|------|-------------|
| Full Name | Text | First and last name |
| Date of Birth | Date | Used to calculate age |
| Sex | Select | Male, Female, Other |
| Gender Identity | Select | Optional, for healthcare preferences |
| Blood Type | Select | A+, A-, B+, B-, AB+, AB-, O+, O-, Unknown |
| Height | Number | In cm or ft/in (user preference) |
| Weight | Number | In kg or lbs (user preference) |
| Profile Photo | Image | Optional avatar |

#### 2. Contact & Location
| Field | Type | Description |
|-------|------|-------------|
| Phone Number | Phone | Primary contact |
| Address | Address | For locating nearby facilities |
| Country | Select | For regional health guidelines |
| Preferred Language | Select | For AI responses |
| Time Zone | Select | For appointment reminders |

#### 3. Emergency Information (Critical)
| Field | Type | Description |
|-------|------|-------------|
| Emergency Contact 1 | Contact | Name, relationship, phone |
| Emergency Contact 2 | Contact | Backup contact |
| Medical Alert | Text | Critical info (diabetic, pacemaker, etc.) |
| Organ Donor Status | Boolean | Yes/No/Undeclared |
| DNR Status | Boolean | Do Not Resuscitate preference |
| Preferred Hospital | Text | Where to be taken in emergency |

#### 4. Medical History
| Field | Type | Description |
|-------|------|-------------|
| Known Allergies | Multi-select + Text | Food, drug, environmental, other |
| Allergy Severity | Select per allergy | Mild, Moderate, Severe, Life-threatening |
| Chronic Conditions | Multi-select + Text | Diabetes, hypertension, asthma, etc. |
| Past Surgeries | List | Surgery name, date, hospital |
| Hospitalizations | List | Reason, date, duration |
| Family Medical History | Structured | Conditions by relation (parent, sibling) |
| Genetic Conditions | Text | Known hereditary conditions |

#### 5. Current Health
| Field | Type | Description |
|-------|------|-------------|
| Current Medications | List | Name, dosage, frequency, start date |
| Supplements | List | Vitamins, herbs, etc. |
| Medical Devices | List | Pacemaker, insulin pump, hearing aid, etc. |
| Mobility Aids | Multi-select | Wheelchair, walker, cane, etc. |
| Vision | Select | Normal, glasses, contacts, legally blind |
| Hearing | Select | Normal, hearing aid, deaf |

#### 6. Healthcare Providers
| Field | Type | Description |
|-------|------|-------------|
| Primary Care Physician | Contact | Name, clinic, phone |
| Specialists | List | Specialty, doctor name, clinic |
| Pharmacy | Contact | Preferred pharmacy name, address |
| Dentist | Contact | Name, clinic, phone |
| Insurance Provider | Text | Company, policy number |
| Insurance Group | Text | Group number |

#### 7. Lifestyle (For Better AI Insights)
| Field | Type | Description |
|-------|------|-------------|
| Smoking Status | Select | Never, Former, Current, frequency |
| Alcohol Use | Select | Never, Occasional, Moderate, Heavy |
| Exercise Frequency | Select | None, Light, Moderate, Active |
| Diet Type | Select | Regular, Vegetarian, Vegan, Keto, etc. |
| Sleep Hours | Number | Average per night |
| Occupation | Text | For occupational health context |
| Stress Level | Select | Low, Moderate, High |

---

## Child-Specific Profile Fields

For dependents under 18, additional fields are available:

#### Birth Information
| Field | Type | Description |
|-------|------|-------------|
| Birth Weight | Number | Weight at birth |
| Birth Length | Number | Length at birth |
| Gestational Age | Number | Weeks at birth (for preemies) |
| APGAR Score | Number | If known |
| Birth Complications | Text | Any issues during delivery |
| Birth Hospital | Text | Where they were born |

#### Development & Growth
| Field | Type | Description |
|-------|------|-------------|
| Current Height | Number | Most recent measurement |
| Current Weight | Number | Most recent measurement |
| Head Circumference | Number | For infants |
| Growth Percentile | Auto-calculated | Based on CDC/WHO charts |
| Developmental Milestones | Checklist | First words, walking, etc. |

#### Vaccination Record
| Field | Type | Description |
|-------|------|-------------|
| Vaccination History | List | Vaccine name, date, lot number |
| Next Due Vaccines | Auto-calculated | Based on schedule |
| Vaccine Reactions | List | Any adverse reactions |
| Exemptions | List | Medical/religious exemptions |

#### School & Childcare
| Field | Type | Description |
|-------|------|-------------|
| School/Daycare | Text | Name and contact |
| Grade/Class | Text | Current grade |
| School Nurse | Contact | Name and phone |
| Special Needs | Text | IEP, 504 plan, accommodations |
| Sports/Activities | List | For injury context |

#### Pediatric Healthcare
| Field | Type | Description |
|-------|------|-------------|
| Pediatrician | Contact | Name, clinic, phone |
| Last Checkup | Date | Most recent well-child visit |
| Next Checkup Due | Date | Scheduled/recommended |

---

## User Stories

### As a Parent
- I want to add my children to my account so I can manage their health records
- I want to upload my child's vaccination records, lab results, and doctor visit notes
- I want to ask questions like "When was my son's last tetanus shot?"
- I want to track my daughter's growth charts and developmental milestones
- I want to compare siblings' health data (e.g., "Compare allergy history")
- I want to keep my children's blood types on file for emergencies

### As a Caretaker
- I want to manage health records for elderly parents I care for
- I want to share access with other family members (spouse, siblings)
- I want to set up emergency contacts and critical health information
- I want to track their medications and doctor appointments

### As a User
- I want to complete my health profile after signing up
- I want to update my profile information at any time
- I want the AI to use my profile for better, personalized answers
- I want to easily switch between my records and my dependents' records
- I want clear visual indication of whose records I'm viewing
- I want my dependents' data to be as secure as my own

---

## Profile Completion Flow (After Signup)

### Onboarding Steps

```
┌────────────────────────────────────────────────────────────────┐
│                    Complete Your Profile                       │
│                                                                │
│  Help MedMemory give you better, personalized health insights │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  ● Basic Info        ○ Medical History    ○ Lifestyle   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Step 1 of 5: Basic Information                               │
│  ───────────────────────────────────────────────────────────  │
│                                                                │
│  Date of Birth: [__/__/____]                                  │
│                                                                │
│  Sex:  ○ Male  ○ Female  ○ Other                             │
│                                                                │
│  Blood Type:  [Select ▼]                                      │
│               ┌─────────────┐                                 │
│               │ A+          │                                 │
│               │ A-          │                                 │
│               │ B+          │                                 │
│               │ B-          │                                 │
│               │ AB+         │                                 │
│               │ AB-         │                                 │
│               │ O+          │                                 │
│               │ O-          │                                 │
│               │ Don't know  │                                 │
│               └─────────────┘                                 │
│                                                                │
│  Height: [___] cm  /  [__] ft [__] in                         │
│  Weight: [___] kg  /  [___] lbs                               │
│                                                                │
│            [Skip for now]  [Continue →]                       │
│                                                                │
│  ────────────────────────────────────────────────────────────  │
│  You can always update this later in Settings > My Profile    │
└────────────────────────────────────────────────────────────────┘
```

### Profile Completion Progress

```
┌─────────────────────────────────────────────────────┐
│  Your Profile                           85% Complete │
│  ═══════════════════════════════════░░░░            │
│                                                      │
│  ✓ Basic Info                                       │
│  ✓ Emergency Contacts                               │
│  ✓ Medical History                                  │
│  ○ Healthcare Providers  ← Complete this section   │
│  ○ Lifestyle                                        │
└─────────────────────────────────────────────────────┘
```

---

## Profile Settings UI

### My Profile Page

```
┌────────────────────────────────────────────────────────────────┐
│  My Profile                                    [Edit Profile]  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────┐  Bryan Smith                                     │
│  │  👤     │  Age 35 · Male · O+ Blood Type                   │
│  │  Photo  │  Height: 5'10" · Weight: 175 lbs                 │
│  └─────────┘  Member since January 2026                       │
│                                                                │
│  ═══════════════════════════════════════════════════════════  │
│                                                                │
│  📋 Quick Stats                                               │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐   │
│  │ 12          │ 3           │ 2           │ 5           │   │
│  │ Documents   │ Conditions  │ Allergies   │ Medications │   │
│  └─────────────┴─────────────┴─────────────┴─────────────┘   │
│                                                                │
│  ═══════════════════════════════════════════════════════════  │
│                                                                │
│  [Basic Info]  [Medical]  [Emergency]  [Providers]  [Family] │
│  ─────────────────────────────────────────────────────────── │
│                                                                │
│  Basic Information                           [Edit ✏️]        │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Full Name:      Bryan Smith                              ││
│  │ Date of Birth:  March 15, 1990 (Age 35)                 ││
│  │ Sex:            Male                                     ││
│  │ Blood Type:     O Positive (O+)                         ││
│  │ Height:         5'10" (178 cm)                          ││
│  │ Weight:         175 lbs (79 kg)                         ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│  Emergency Information                       [Edit ✏️]        │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ ⚠️ Medical Alert: None                                   ││
│  │                                                          ││
│  │ Emergency Contact 1:                                     ││
│  │   Jane Smith (Spouse) · +1 555-123-4567                 ││
│  │                                                          ││
│  │ Emergency Contact 2:                                     ││
│  │   Not set · [Add contact]                               ││
│  │                                                          ││
│  │ Preferred Hospital: City General Hospital               ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Edit Profile Modal

```
┌────────────────────────────────────────────────────────────────┐
│  Edit Medical History                                        ✕ │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Known Allergies                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ × Penicillin (Severe - Anaphylaxis)                      ││
│  │ × Shellfish (Moderate - Hives)                           ││
│  │ × Pollen (Mild - Seasonal)                               ││
│  │                                                          ││
│  │ [+ Add Allergy]                                          ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│  Chronic Conditions                                           │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ × Type 2 Diabetes (Diagnosed 2020)                       ││
│  │ × Hypertension (Diagnosed 2018)                          ││
│  │                                                          ││
│  │ [+ Add Condition]                                        ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│  Current Medications                                          │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ × Metformin 500mg - Twice daily                         ││
│  │ × Lisinopril 10mg - Once daily                          ││
│  │ × Atorvastatin 20mg - Once daily at bedtime             ││
│  │                                                          ││
│  │ [+ Add Medication]                                       ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│                              [Cancel]  [Save Changes]         │
└────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Enhanced Patient Model

```sql
-- Enhanced patients table with comprehensive health profile
ALTER TABLE patients ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS sex VARCHAR(20);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS gender_identity VARCHAR(50);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS blood_type VARCHAR(5);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS height_cm DECIMAL(5,2);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS weight_kg DECIMAL(5,2);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(255);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(255);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS state VARCHAR(100);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS country VARCHAR(100);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10) DEFAULT 'en';
ALTER TABLE patients ADD COLUMN IF NOT EXISTS timezone VARCHAR(50);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS profile_photo_url VARCHAR(500);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_minor BOOLEAN DEFAULT false;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS profile_completed_at TIMESTAMP;

-- Emergency information
CREATE TABLE patient_emergency_info (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medical_alert TEXT,
    organ_donor BOOLEAN,
    dnr_status BOOLEAN,
    preferred_hospital VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(patient_id)
);

-- Emergency contacts
CREATE TABLE emergency_contacts (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    is_primary BOOLEAN DEFAULT false,
    priority_order INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Allergies
CREATE TABLE patient_allergies (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    allergen VARCHAR(255) NOT NULL,
    allergy_type VARCHAR(50) NOT NULL, -- 'food', 'drug', 'environmental', 'other'
    severity VARCHAR(20) NOT NULL, -- 'mild', 'moderate', 'severe', 'life_threatening'
    reaction TEXT,
    diagnosed_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Chronic conditions
CREATE TABLE patient_conditions (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    condition_name VARCHAR(255) NOT NULL,
    icd_code VARCHAR(20), -- ICD-10 code if known
    diagnosed_date DATE,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'resolved', 'in_remission'
    severity VARCHAR(20),
    treating_physician VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Current medications
CREATE TABLE patient_medications (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    medication_name VARCHAR(255) NOT NULL,
    dosage VARCHAR(100),
    frequency VARCHAR(100),
    route VARCHAR(50), -- 'oral', 'injection', 'topical', etc.
    prescribing_physician VARCHAR(255),
    pharmacy VARCHAR(255),
    start_date DATE,
    end_date DATE,
    is_active BOOLEAN DEFAULT true,
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Healthcare providers
CREATE TABLE patient_providers (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    provider_type VARCHAR(50) NOT NULL, -- 'pcp', 'specialist', 'dentist', 'pharmacy', 'hospital'
    specialty VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    clinic_name VARCHAR(255),
    phone VARCHAR(20),
    fax VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    is_primary BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Surgeries and hospitalizations
CREATE TABLE patient_procedures (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    procedure_type VARCHAR(50) NOT NULL, -- 'surgery', 'hospitalization', 'procedure'
    name VARCHAR(255) NOT NULL,
    date DATE,
    hospital VARCHAR(255),
    surgeon VARCHAR(255),
    reason TEXT,
    outcome TEXT,
    complications TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Family medical history
CREATE TABLE family_history (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    relation VARCHAR(50) NOT NULL, -- 'mother', 'father', 'sibling', 'grandparent', etc.
    condition VARCHAR(255) NOT NULL,
    age_of_onset INTEGER,
    is_deceased BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Lifestyle factors
CREATE TABLE patient_lifestyle (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    smoking_status VARCHAR(20), -- 'never', 'former', 'current'
    smoking_frequency VARCHAR(50),
    alcohol_use VARCHAR(20), -- 'never', 'occasional', 'moderate', 'heavy'
    exercise_frequency VARCHAR(20), -- 'none', 'light', 'moderate', 'active'
    diet_type VARCHAR(50),
    sleep_hours DECIMAL(3,1),
    occupation VARCHAR(255),
    stress_level VARCHAR(20),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(patient_id)
);

-- Insurance information
CREATE TABLE patient_insurance (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    provider_name VARCHAR(255) NOT NULL,
    policy_number VARCHAR(100),
    group_number VARCHAR(100),
    subscriber_name VARCHAR(255),
    subscriber_dob DATE,
    relationship_to_subscriber VARCHAR(50),
    effective_date DATE,
    expiration_date DATE,
    is_primary BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Child-specific: Vaccinations
CREATE TABLE patient_vaccinations (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    vaccine_name VARCHAR(255) NOT NULL,
    dose_number INTEGER,
    date_administered DATE NOT NULL,
    administered_by VARCHAR(255),
    location VARCHAR(255),
    lot_number VARCHAR(100),
    expiration_date DATE,
    site VARCHAR(50), -- 'left arm', 'right thigh', etc.
    reaction TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Child-specific: Growth measurements
CREATE TABLE growth_measurements (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    measurement_date DATE NOT NULL,
    age_months INTEGER,
    height_cm DECIMAL(5,2),
    weight_kg DECIMAL(5,2),
    head_circumference_cm DECIMAL(5,2),
    height_percentile INTEGER,
    weight_percentile INTEGER,
    bmi DECIMAL(4,2),
    bmi_percentile INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Child-specific: Developmental milestones
CREATE TABLE developmental_milestones (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    milestone_name VARCHAR(255) NOT NULL,
    category VARCHAR(50), -- 'motor', 'language', 'social', 'cognitive'
    achieved_date DATE,
    expected_age_months INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Dependent relationships
CREATE TABLE patient_relationships (
    id SERIAL PRIMARY KEY,
    caretaker_patient_id INTEGER NOT NULL REFERENCES patients(id),
    dependent_patient_id INTEGER NOT NULL REFERENCES patients(id),
    relationship_type VARCHAR(50) NOT NULL, -- 'parent', 'guardian', 'caretaker', 'spouse'
    is_primary_caretaker BOOLEAN DEFAULT true,
    can_edit BOOLEAN DEFAULT true,
    can_share BOOLEAN DEFAULT false,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(caretaker_patient_id, dependent_patient_id)
);
```

---

## API Endpoints

### Profile Management

```yaml
# Get current user's complete profile
GET /api/v1/profile
Response:
  basic_info:
    full_name: "Bryan Smith"
    date_of_birth: "1990-03-15"
    age: 35
    sex: "male"
    blood_type: "O+"
    height_cm: 178
    weight_kg: 79
  emergency_info:
    medical_alert: null
    emergency_contacts:
      - name: "Jane Smith"
        relationship: "spouse"
        phone: "+1 555-123-4567"
    preferred_hospital: "City General"
  medical_history:
    allergies:
      - allergen: "Penicillin"
        severity: "severe"
        reaction: "Anaphylaxis"
    conditions:
      - name: "Type 2 Diabetes"
        status: "active"
        diagnosed_date: "2020-05-01"
    medications:
      - name: "Metformin"
        dosage: "500mg"
        frequency: "twice daily"
  profile_completion: 85

# Update basic profile info
PUT /api/v1/profile/basic
Body:
  date_of_birth: "1990-03-15"
  sex: "male"
  blood_type: "O+"
  height_cm: 178
  weight_kg: 79

# Update emergency information
PUT /api/v1/profile/emergency
Body:
  medical_alert: "Diabetic - carries insulin"
  organ_donor: true
  preferred_hospital: "City General Hospital"

# Add/update emergency contact
POST /api/v1/profile/emergency-contacts
Body:
  name: "Jane Smith"
  relationship: "spouse"
  phone: "+1 555-123-4567"
  is_primary: true

# Manage allergies
GET /api/v1/profile/allergies
POST /api/v1/profile/allergies
PUT /api/v1/profile/allergies/{allergy_id}
DELETE /api/v1/profile/allergies/{allergy_id}

# Manage conditions
GET /api/v1/profile/conditions
POST /api/v1/profile/conditions
PUT /api/v1/profile/conditions/{condition_id}
DELETE /api/v1/profile/conditions/{condition_id}

# Manage medications
GET /api/v1/profile/medications
POST /api/v1/profile/medications
PUT /api/v1/profile/medications/{medication_id}
DELETE /api/v1/profile/medications/{medication_id}

# Manage healthcare providers
GET /api/v1/profile/providers
POST /api/v1/profile/providers
PUT /api/v1/profile/providers/{provider_id}
DELETE /api/v1/profile/providers/{provider_id}

# Update lifestyle factors
PUT /api/v1/profile/lifestyle
Body:
  smoking_status: "never"
  alcohol_use: "occasional"
  exercise_frequency: "moderate"
  diet_type: "regular"
  sleep_hours: 7.5

# Get profile completion status
GET /api/v1/profile/completion
Response:
  overall_percentage: 85
  sections:
    - name: "basic_info"
      complete: true
      percentage: 100
    - name: "emergency"
      complete: true
      percentage: 100
    - name: "medical_history"
      complete: true
      percentage: 100
    - name: "providers"
      complete: false
      percentage: 50
      missing: ["dentist", "pharmacy"]
    - name: "lifestyle"
      complete: false
      percentage: 60
```

### Dependents Management

```yaml
# List dependents for current user
GET /api/v1/dependents
Response:
  - id: 1
    full_name: "Emma Smith"
    date_of_birth: "2018-03-15"
    age: 7
    sex: "female"
    blood_type: "A+"
    relationship: "child"
    avatar_color: "#4CAF50"
    profile_completion: 90
    recent_activity: "Lab results uploaded 2 days ago"

# Add a new dependent with full profile
POST /api/v1/dependents
Body:
  first_name: "Emma"
  last_name: "Smith"
  date_of_birth: "2018-03-15"
  sex: "female"
  blood_type: "A+"
  relationship_type: "child"
  birth_weight_kg: 3.2
  birth_length_cm: 50
  pediatrician: "Dr. Sarah Johnson"
Response:
  id: 1
  full_name: "Emma Smith"
  message: "Dependent added successfully"

# Get dependent's complete profile
GET /api/v1/dependents/{dependent_id}/profile

# Update dependent's profile
PUT /api/v1/dependents/{dependent_id}/profile
PUT /api/v1/dependents/{dependent_id}/profile/basic
PUT /api/v1/dependents/{dependent_id}/profile/medical

# Manage dependent's allergies
GET /api/v1/dependents/{dependent_id}/allergies
POST /api/v1/dependents/{dependent_id}/allergies
DELETE /api/v1/dependents/{dependent_id}/allergies/{allergy_id}

# Manage dependent's vaccinations
GET /api/v1/dependents/{dependent_id}/vaccinations
POST /api/v1/dependents/{dependent_id}/vaccinations
Response:
  vaccinations:
    - id: 1
      vaccine_name: "DTaP"
      dose_number: 5
      date_administered: "2025-09-15"
      next_due: null
  upcoming:
    - vaccine_name: "Flu Shot"
      due_date: "2026-10-01"
      recommended_by: "CDC Schedule"

# Track growth measurements
GET /api/v1/dependents/{dependent_id}/growth
POST /api/v1/dependents/{dependent_id}/growth
Body:
  measurement_date: "2026-01-15"
  height_cm: 119.4
  weight_kg: 23.6
Response:
  measurement_id: 1
  height_percentile: 75
  weight_percentile: 70
  bmi: 16.5
  bmi_percentile: 55
  growth_status: "normal"

# Track developmental milestones
GET /api/v1/dependents/{dependent_id}/milestones
POST /api/v1/dependents/{dependent_id}/milestones
Body:
  milestone_name: "Rides bicycle without training wheels"
  category: "motor"
  achieved_date: "2025-06-15"

# Remove dependent (unlink, doesn't delete data)
DELETE /api/v1/dependents/{dependent_id}

# Share access with another user
POST /api/v1/dependents/{dependent_id}/share
Body:
  email: "spouse@example.com"
  access_level: "edit"
  
# Get family overview (all dependents' key health metrics)
GET /api/v1/family/overview
Response:
  members:
    - id: 1
      name: "Emma Smith"
      age: 7
      sex: "female"
      blood_type: "A+"
      upcoming: "Annual checkup in 2 weeks"
      alerts: ["Flu shot due in October"]
      growth_status: "On track (75th percentile)"
    - id: 2
      name: "Jack Smith"  
      age: 4
      sex: "male"
      blood_type: "O+"
      upcoming: null
      alerts: []
      growth_status: "On track (50th percentile)"
```

---

## UI/UX Design

### 1. Profile Switcher (Top Bar)

```
┌─────────────────────────────────────────────────────┐
│  ● MedMemory          [👤 Bryan ▼]  [⚙️] [Log Out]  │
└─────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │  👤 My Health           │ ← Current
              │  ─────────────────────  │
              │  👶 Emma (7)            │
              │  👦 Jack (4)            │
              │  ─────────────────────  │
              │  ＋ Add Family Member   │
              └─────────────────────────┘
```

### 2. Add Dependent Modal

```
┌────────────────────────────────────────────────────────┐
│                  Add Family Member                   ✕ │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Who would you like to add?                           │
│                                                        │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐      │
│  │  👶    │  │  👦    │  │  👧    │  │  👴    │      │
│  │ Child  │  │  Teen  │  │ Adult  │  │ Senior │      │
│  └────────┘  └────────┘  └────────┘  └────────┘      │
│                                                        │
│  First Name: [______________]                          │
│  Last Name:  [______________]                          │
│  Date of Birth: [__/__/____]                          │
│  Gender: [Select ▼]                                   │
│  Relationship: [Child ▼]                              │
│                                                        │
│  [ ] I am the legal guardian of this person           │
│                                                        │
│            [Cancel]  [Add Family Member]              │
└────────────────────────────────────────────────────────┘
```

### 3. Family Dashboard View

```
┌────────────────────────────────────────────────────────────────┐
│  Family Health Overview                                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ 👤 Bryan     │  │ 👶 Emma (7)  │  │ 👦 Jack (4)  │        │
│  │              │  │              │  │              │        │
│  │ 3 documents  │  │ 5 documents  │  │ 2 documents  │        │
│  │ Last: 1w ago │  │ Last: 2d ago │  │ Last: 1m ago │        │
│  │              │  │              │  │              │        │
│  │ ⚠️ 1 alert   │  │ 💉 Vax due   │  │ ✓ Up to date │        │
│  │              │  │              │  │              │        │
│  │ [View →]     │  │ [View →]     │  │ [View →]     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                │
│  [＋ Add Family Member]                                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 4. Viewing Dependent's Records

When viewing a dependent's records, show a clear banner:

```
┌────────────────────────────────────────────────────────────────┐
│  👶 Viewing: Emma Smith (Age 7)              [Switch Person ▼] │
│  ────────────────────────────────────────────────────────────  │
│                                                                │
│  [Chat] [Documents] [Records] [Timeline]                       │
│                                                                │
```

### 5. Child-Specific Features

For children, show age-appropriate metrics:

```
┌────────────────────────────────────────────────────────────────┐
│  Emma's Health Summary                                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  📊 Growth Tracking                                            │
│  ┌─────────────────────────────────────────────────┐          │
│  │  Height: 47" (75th percentile)                  │          │
│  │  Weight: 52 lbs (70th percentile)              │          │
│  │  [View Growth Chart]                            │          │
│  └─────────────────────────────────────────────────┘          │
│                                                                │
│  💉 Vaccination Status                                         │
│  ┌─────────────────────────────────────────────────┐          │
│  │  ✓ DTaP (5 doses) - Complete                    │          │
│  │  ✓ MMR (2 doses) - Complete                     │          │
│  │  ⚠️ Flu shot - Due in October                    │          │
│  │  [View All Vaccinations]                        │          │
│  └─────────────────────────────────────────────────┘          │
│                                                                │
│  🏥 Upcoming                                                   │
│  • Annual checkup - March 15, 2026                            │
│  • Dentist - April 2, 2026                                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core Dependent Management (MVP)

**Backend:**
1. Create `patient_relationships` table migration
2. Add `DependentService` with CRUD operations
3. Create API endpoints: list, add, update, remove dependents
4. Update patient authorization to check relationships

**Frontend:**
1. Add profile switcher dropdown in TopBar
2. Create "Add Dependent" modal
3. Update patient context to handle dependents
4. Show dependent indicator when viewing their records

**Effort:** ~3-5 days

### Phase 2: Family Dashboard

**Backend:**
1. Create `/family/overview` endpoint
2. Add dependent-specific insights (vaccinations, growth)
3. Implement age-based metric calculations

**Frontend:**
1. Create Family Dashboard view
2. Add family member cards with key metrics
3. Quick navigation between family members

**Effort:** ~3-4 days

### Phase 3: Sharing & Collaboration

**Backend:**
1. Create `shared_access` table migration
2. Implement invite system (email-based)
3. Add access level controls
4. Create audit logging for compliance

**Frontend:**
1. Add "Share Access" modal
2. Show shared users for each dependent
3. Manage permissions UI

**Effort:** ~4-5 days

### Phase 4: Child-Specific Features

**Backend:**
1. Growth chart calculations (CDC percentiles)
2. Vaccination schedule tracking
3. Developmental milestone checklist
4. Pediatric-specific insights

**Frontend:**
1. Growth chart visualization
2. Vaccination tracker UI
3. Milestone checklist
4. Age-appropriate health tips

**Effort:** ~5-7 days

---

## Example Conversations

### Parent asking about child's health

```
User: When was Emma's last vaccination?

MedMemory: Emma received her last vaccination on September 12, 2025:
- Flu shot (seasonal influenza)

Her vaccination record shows all routine childhood vaccinations 
are up to date. The next recommended vaccination is:
- Flu shot (due October 2026)
```

### Comparing siblings

```
User: Compare Emma and Jack's allergy history

MedMemory: Here's a comparison of allergy information:

**Emma (7):**
- Peanut allergy (diagnosed 2022, carries EpiPen)
- Seasonal allergies (pollen, treated with Zyrtec)

**Jack (4):**
- No known food allergies
- Mild eczema (uses hydrocortisone cream as needed)

Note: Both children have had allergy testing. Emma's peanut 
allergy was confirmed via skin prick test in March 2022.
```

### Growth tracking

```
User: How is Jack's growth compared to other kids his age?

MedMemory: Based on Jack's last checkup (January 2026):

**Height:** 41 inches (50th percentile)
- Average for his age

**Weight:** 38 lbs (55th percentile)  
- Slightly above average, healthy range

**Growth Trend:**
Jack has been tracking consistently along the 50th percentile 
for height since age 2. His growth pattern is normal and steady.

[View full growth chart]
```

---

## Security Considerations

### Authorization Rules

```python
# Authorization checks for dependent access
class DependentAuthorization:
    
    async def can_access_dependent(
        self, user_id: int, dependent_id: int
    ) -> bool:
        """Check if user can access dependent's records."""
        # Check if user is primary caretaker
        relationship = await self.get_relationship(user_id, dependent_id)
        if relationship and relationship.can_view:
            return True
        
        # Check shared access
        shared = await self.get_shared_access(user_id, dependent_id)
        if shared and (not shared.expires_at or shared.expires_at > now()):
            return True
        
        return False
    
    async def can_edit_dependent(
        self, user_id: int, dependent_id: int
    ) -> bool:
        """Check if user can edit dependent's records."""
        relationship = await self.get_relationship(user_id, dependent_id)
        if relationship and relationship.can_edit:
            return True
        
        shared = await self.get_shared_access(user_id, dependent_id)
        if shared and shared.access_level in ('edit', 'full'):
            return True
        
        return False
```

### Audit Logging

All access to dependent records should be logged:

```python
async def log_dependent_access(
    user_id: int,
    patient_id: int,
    action: str,
    resource_type: str = None,
    resource_id: int = None,
):
    """Log access to dependent's records for compliance."""
    await db.execute(
        insert(DependentAccessLog).values(
            user_id=user_id,
            patient_id=patient_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=get_client_ip(),
        )
    )
```

### Data Isolation

- Dependents' data is stored in separate patient records
- Clear separation in database queries
- No data leakage between family members' records
- Each dependent has their own document storage folder

---

## Privacy & Legal Considerations

### For Minors (Under 18)
- Parent/guardian must confirm legal relationship
- Data belongs to the child, managed by guardian
- Consider age of consent for medical records (varies by jurisdiction)
- At age 18, prompt transfer of account control to the now-adult

### For Adults Under Care
- Require explicit consent or legal documentation
- Power of attorney upload option
- Clear indication of caretaker relationship
- Option for care recipient to revoke access

### HIPAA Considerations
- Audit trail for all dependent access
- Minimum necessary access principle
- Secure sharing mechanisms
- Data retention policies

---

## Quick Start Implementation

### Step 1: Add Migration

```python
# backend/alembic/versions/xxx_add_dependents.py

def upgrade():
    op.create_table(
        'patient_relationships',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('caretaker_patient_id', sa.Integer(), 
                  sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('dependent_patient_id', sa.Integer(), 
                  sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False),
        sa.Column('is_primary_caretaker', sa.Boolean(), default=True),
        sa.Column('can_edit', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('caretaker_patient_id', 'dependent_patient_id'),
    )
```

### Step 2: Add API Endpoint

```python
# backend/app/api/dependents.py

@router.get("/dependents", response_model=list[DependentSummary])
async def list_dependents(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all dependents for the current user."""
    # Get user's patient record
    patient = await get_patient_for_user(current_user.id, db)
    
    # Get dependents
    result = await db.execute(
        select(Patient)
        .join(PatientRelationship, 
              PatientRelationship.dependent_patient_id == Patient.id)
        .where(PatientRelationship.caretaker_patient_id == patient.id)
    )
    dependents = result.scalars().all()
    
    return [DependentSummary.from_patient(d) for d in dependents]
```

### Step 3: Add Frontend Switcher

```tsx
// frontend/src/components/ProfileSwitcher.tsx

const ProfileSwitcher = () => {
  const [dependents, setDependents] = useState<Dependent[]>([]);
  const { patientId, setPatientId } = useAppStore();
  
  return (
    <div className="profile-switcher">
      <button className="current-profile">
        {currentProfile?.name || 'My Health'} ▼
      </button>
      <div className="profile-dropdown">
        <ProfileOption 
          label="My Health" 
          onClick={() => setPatientId(myPatientId)} 
          isActive={patientId === myPatientId}
        />
        <hr />
        {dependents.map(dep => (
          <ProfileOption
            key={dep.id}
            label={`${dep.name} (${dep.age})`}
            icon={getAgeIcon(dep.age)}
            onClick={() => setPatientId(dep.patient_id)}
            isActive={patientId === dep.patient_id}
          />
        ))}
        <hr />
        <button onClick={openAddDependentModal}>
          + Add Family Member
        </button>
      </div>
    </div>
  );
};
```

---

## Summary

The Profile & Dependents feature transforms MedMemory from a simple document storage app into a **comprehensive family health platform**:

### Profile Features

| Category | Information Tracked |
|----------|---------------------|
| **Basic Info** | Name, DOB, sex, blood type, height, weight |
| **Emergency** | Medical alerts, emergency contacts, preferred hospital, DNR status |
| **Medical History** | Allergies, chronic conditions, surgeries, family history |
| **Current Health** | Medications, supplements, medical devices |
| **Providers** | PCP, specialists, pharmacy, dentist, insurance |
| **Lifestyle** | Smoking, alcohol, exercise, diet, sleep, stress |

### Family Management Features

| Feature | Benefit |
|---------|---------|
| **Comprehensive Profiles** | Complete health picture for each family member |
| **Multi-profile Switching** | Easy dropdown to switch between family members |
| **Child-specific Tracking** | Growth charts, vaccinations, developmental milestones |
| **Shared Access** | Co-parents can both manage children's health |
| **AI-powered Insights** | "Compare allergies across kids", "Show Emma's growth trend" |
| **Profile Completion** | Guided onboarding to build complete health profile |
| **Secure & Audited** | Full access logging for compliance |

### AI Benefits from Complete Profiles

With comprehensive profile data, MedGemma can provide better answers:

| Question | Without Profile | With Profile |
|----------|-----------------|--------------|
| "Can I take ibuprofen?" | Generic answer | "Be cautious - you have a history of gastric ulcers and are on blood thinners" |
| "What's causing my fatigue?" | List of possibilities | "Given your diabetes, low exercise, and sleep issues, consider these factors..." |
| "Is this medication safe for Emma?" | General info | "Emma weighs 23kg and is allergic to penicillin - this antibiotic is in the same family" |

### Implementation Phases

1. **Phase 1**: Profile fields + onboarding flow (~5-7 days)
2. **Phase 2**: Dependent management + family switching (~3-5 days)
3. **Phase 3**: Child-specific features (growth, vaccinations) (~5-7 days)
4. **Phase 4**: Sharing + advanced family insights (~4-5 days)

---

## Quick Reference: Profile Fields

### Adult Profile (30+ fields)
```
Basic: name, dob, sex, blood_type, height, weight
Emergency: alerts, contacts (2), hospital, organ_donor, dnr
Medical: allergies[], conditions[], surgeries[], family_history[]
Current: medications[], supplements[], devices[]
Providers: pcp, specialists[], pharmacy, dentist, insurance
Lifestyle: smoking, alcohol, exercise, diet, sleep, stress, occupation
```

### Child Profile (40+ fields)
```
All adult fields PLUS:
Birth: weight, length, gestational_age, apgar, complications
Growth: measurements[], percentiles, bmi_tracking
Vaccines: history[], reactions[], exemptions[], next_due[]
Development: milestones[], checkups[], pediatrician
School: name, grade, nurse_contact, special_needs, activities[]
```

---

*"Because a parent's memory shouldn't be the only backup for their child's health history."*

*"Your complete health story, always at your fingertips."*
