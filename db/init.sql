CREATE TABLE IF NOT EXISTS vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    account_number VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user', -- admin, user
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    parsed_data JSONB,
    status VARCHAR(50) DEFAULT 'pending', -- pending, validated, approved, paid, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id),
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50),
    transaction_id VARCHAR(255),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audits (
    id SERIAL PRIMARY KEY,
    request_hash VARCHAR(64) NOT NULL,
    response_hash VARCHAR(64) NOT NULL,
    raw_request TEXT,
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) NOT NULL,
    batch_id VARCHAR(255) NOT NULL,
    vendor VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    date DATE,
    account_number VARCHAR(255),
    ifsc_code VARCHAR(255),
    remarks TEXT,
    status VARCHAR(50) DEFAULT 'NEEDS_APPROVAL', -- EXTRACTED, NEEDS_APPROVAL, NEEDS_REVIEW, QUEUED_FOR_PAYMENT, PAID, FAILED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
