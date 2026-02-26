-- Kitchmatic 데이터베이스 스키마 (PostgreSQL)

-- ========================================
-- 1. 메뉴 테이블
-- ========================================
CREATE TABLE menus (
    id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    available BOOLEAN DEFAULT TRUE,
    description TEXT DEFAULT '',
    image_url VARCHAR(500) DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_price CHECK (price >= 0)
);

-- 초기 데이터
INSERT INTO menus (id, name, price, category, description, image_url) VALUES
    ('M001', '햄치즈샌드위치', 5000, '샌드위치', '', ''),
    ('M002', '머쉬룸샌드위치', 5500, '샌드위치', '', ''),
    ('M003', '올인원샌드위치', 6500, '샌드위치', '', '');

-- ========================================
-- 2. 식재료 테이블
-- ========================================
CREATE TABLE ingredients (
    id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    items_per_box INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 초기 데이터
INSERT INTO ingredients (id, name, unit, category, items_per_box) VALUES
    ('I001', '빵', '장', '빵류', 5),
    ('I002', '치즈', '장', '유제품', 5),
    ('I003', '토마토', 'g', '채소', 300),
    ('I004', '양상추', 'g', '채소', 120),
    ('I005', '햄', '장', '육류', 5),
    ('I006', '버섯', 'g', '채소', 300);

-- ========================================
-- 3. 레시피 테이블
-- ========================================
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    menu_id VARCHAR(10) NOT NULL REFERENCES menus(id),
    name VARCHAR(100) NOT NULL,
    estimated_time_seconds INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_estimated_time CHECK (estimated_time_seconds > 0)
);

CREATE TABLE recipe_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    ingredient_id VARCHAR(10) REFERENCES ingredients(id),
    quantity INTEGER,
    unit VARCHAR(20),
    robot_arm VARCHAR(10) NOT NULL,
    duration_seconds INTEGER,

    CONSTRAINT chk_robot_arm CHECK (robot_arm IN ('ARM_1', 'ARM_2')),
    CONSTRAINT chk_step_order CHECK (step_order > 0),
    UNIQUE (recipe_id, step_order)
);

CREATE INDEX idx_recipe_steps_recipe ON recipe_steps(recipe_id);

-- ========================================
-- 4. 재고 테이블
-- ========================================
CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_id VARCHAR(10) NOT NULL REFERENCES ingredients(id),
    location VARCHAR(20) NOT NULL,
    current_stock INTEGER NOT NULL DEFAULT 0,
    min_threshold INTEGER NOT NULL DEFAULT 2,
    max_capacity INTEGER NOT NULL DEFAULT 10,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_location CHECK (location IN ('STOCK_AREA', 'INGREDIENT_BED')),
    CONSTRAINT chk_stock CHECK (current_stock >= 0),
    UNIQUE (ingredient_id, location)
);

CREATE TABLE inventory_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inventory_id UUID NOT NULL REFERENCES inventory(id),
    transaction_type VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    before_stock INTEGER NOT NULL,
    after_stock INTEGER NOT NULL,
    order_id UUID,
    robot_id UUID,
    transaction_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_transaction_type CHECK (transaction_type IN (
        'REPLENISHMENT', 'CONSUMPTION', 'REPLACEMENT'
    ))
);

CREATE INDEX idx_inv_trans_inventory ON inventory_transactions(inventory_id);
CREATE INDEX idx_inv_trans_time ON inventory_transactions(transaction_at DESC);

-- ========================================
-- 5. 로봇 테이블
-- ========================================
CREATE TABLE robots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'IDLE',
    ip_address VARCHAR(15) NOT NULL,
    port INTEGER NOT NULL,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_robot_type CHECK (type IN (
        'ARM_1', 'ARM_2', 'SERVING_BOT_1', 'SERVING_BOT_2', 'SERVING_BOT_3'
    )),
    CONSTRAINT chk_robot_status CHECK (status IN (
        'IDLE', 'BUSY', 'ERROR', 'HALTED'
    ))
);

-- 초기 데이터
INSERT INTO robots (name, type, ip_address, port) VALUES
    ('로봇팔 1', 'ARM_1', '192.168.1.101', 5001),
    ('로봇팔 2', 'ARM_2', '192.168.1.102', 5002),
    ('서빙로봇 1', 'SERVING_BOT_1', '192.168.1.201', 5011),
    ('서빙로봇 2', 'SERVING_BOT_2', '192.168.1.202', 5012),
    ('서빙로봇 3', 'SERVING_BOT_3', '192.168.1.203', 5013);

-- ========================================
-- 6. 주문 테이블
-- ========================================
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_number VARCHAR(10) NOT NULL,
    menu_id VARCHAR(10) NOT NULL REFERENCES menus(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    voice_order BOOLEAN DEFAULT FALSE,
    assigned_robot_arm_id UUID REFERENCES robots(id),
    assigned_serving_bot_id UUID REFERENCES robots(id),

    CONSTRAINT chk_status CHECK (status IN (
        'PENDING', 'CONFIRMED', 'COOKING', 'READY', 'INSPECTED',
        'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED'
    )),
    CONSTRAINT chk_quantity CHECK (quantity > 0)
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_table_number ON orders(table_number);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);

-- ========================================
-- 7. 품질 검사 테이블
-- ========================================
CREATE TABLE quality_check_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    status VARCHAR(20) NOT NULL,
    confidence_score FLOAT,
    checked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    attempt_number INTEGER NOT NULL DEFAULT 1,
    robot_arm_id UUID REFERENCES robots(id),

    CONSTRAINT chk_quality_status CHECK (status IN ('NORMAL', 'ABNORMAL')),
    CONSTRAINT chk_confidence CHECK (confidence_score >= 0 AND confidence_score <= 100),
    CONSTRAINT chk_attempt CHECK (attempt_number > 0)
);

CREATE INDEX idx_quality_order ON quality_check_results(order_id);
CREATE INDEX idx_quality_status ON quality_check_results(status);
CREATE INDEX idx_quality_time ON quality_check_results(checked_at DESC);

-- ========================================
-- Foreign Key 추가 (주문 → 재고 이력)
-- ========================================
ALTER TABLE inventory_transactions
    ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id);

ALTER TABLE inventory_transactions
    ADD CONSTRAINT fk_robot FOREIGN KEY (robot_id) REFERENCES robots(id);
