"""
데이터 모델 정의
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"          # 대기중
    CONFIRMED = "confirmed"      # 확인됨
    COOKING = "cooking"          # 조리중
    READY = "ready"              # 조리완료
    INSPECTED = "inspected"      # 검수완료
    DELIVERING = "delivering"    # 배달중
    DELIVERED = "delivered"      # 배달완료
    COMPLETED = "completed"      # 수령완료
    CANCELLED = "cancelled"      # 취소됨
    HALTED = "halted"            # 일시중지 (관리자 개입)


@dataclass
class MenuItem:
    """메뉴 아이템"""
    menu_id: str
    name: str
    price: int
    description: str = ""
    image_url: str = ""
    available: bool = True       # 제공 가능 여부 (재고 등)
    category: str = ""

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'menu_id': self.menu_id,
            'name': self.name,
            'price': self.price,
            'description': self.description,
            'image_url': self.image_url,
            'available': self.available,
            'category': self.category
        }

    @staticmethod
    def from_dict(data: dict) -> 'MenuItem':
        """딕셔너리에서 생성"""
        return MenuItem(
            menu_id=data.get('menu_id', ''),
            name=data.get('name', ''),
            price=data.get('price', 0),
            description=data.get('description', ''),
            image_url=data.get('image_url', ''),
            available=data.get('available', True),
            category=data.get('category', '')
        )


@dataclass
class OrderItem:
    """주문 아이템 (장바구니 항목)"""
    menu_item: MenuItem
    quantity: int = 1
    sauce: str = ""  # 소스 선택 (소스선택x, 마요네즈, 케찹, 머스타드)

    def get_subtotal(self) -> int:
        """소계 계산"""
        return self.menu_item.price * self.quantity

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'menu_id': self.menu_item.menu_id,
            'menu_name': self.menu_item.name,
            'price': self.menu_item.price,
            'quantity': self.quantity,
            'subtotal': self.get_subtotal(),
            'sauce': self.sauce
        }


@dataclass
class Order:
    """주문"""
    table_number: int
    items: List[OrderItem] = field(default_factory=list)
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    total_price: int = 0

    def calculate_total(self) -> int:
        """총 금액 계산"""
        self.total_price = sum(item.get_subtotal() for item in self.items)
        return self.total_price

    def add_item(self, menu_item: MenuItem, quantity: int = 1):
        """아이템 추가"""
        # 이미 같은 메뉴가 있으면 수량만 증가
        for item in self.items:
            if item.menu_item.menu_id == menu_item.menu_id:
                item.quantity += quantity
                self.calculate_total()
                return

        # 없으면 새로 추가
        self.items.append(OrderItem(menu_item, quantity))
        self.calculate_total()

    def remove_item(self, menu_id: str):
        """아이템 제거"""
        self.items = [item for item in self.items if item.menu_item.menu_id != menu_id]
        self.calculate_total()

    def update_quantity(self, menu_id: str, quantity: int):
        """수량 변경"""
        for item in self.items:
            if item.menu_item.menu_id == menu_id:
                if quantity <= 0:
                    self.remove_item(menu_id)
                else:
                    item.quantity = quantity
                break
        self.calculate_total()

    def clear(self):
        """주문 초기화"""
        self.items.clear()
        self.total_price = 0

    def to_dict(self):
        """딕셔너리로 변환 (TCP 전송용)"""
        return {
            'order_id': self.order_id,
            'table_number': self.table_number,
            'items': [item.to_dict() for item in self.items],
            'total_price': self.total_price,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class VoiceRecognitionState:
    """음성 인식 상태"""
    is_listening: bool = False
    recognized_text: str = ""
    confidence: float = 0.0


# ==================== Admin GUI 전용 모델 ====================

@dataclass
class Ingredient:
    """재료"""
    ingredient_id: str
    name: str
    unit: str  # 단위 (g, ml, 개 등)
    allergens: List[str] = field(default_factory=list)  # 알레르기 유발 물질

    def to_dict(self):
        return {
            'ingredient_id': self.ingredient_id,
            'name': self.name,
            'unit': self.unit,
            'allergens': self.allergens
        }

    @staticmethod
    def from_dict(data: dict) -> 'Ingredient':
        return Ingredient(
            ingredient_id=data.get('ingredient_id', ''),
            name=data.get('name', ''),
            unit=data.get('unit', ''),
            allergens=data.get('allergens', [])
        )


@dataclass
class RecipeIngredient:
    """레시피에 필요한 재료"""
    ingredient: Ingredient
    quantity: float  # 필요 수량

    def to_dict(self):
        return {
            'ingredient_id': self.ingredient.ingredient_id,
            'ingredient_name': self.ingredient.name,
            'quantity': self.quantity,
            'unit': self.ingredient.unit
        }


@dataclass
class CookingStep:
    """조리 단계"""
    step_number: int
    description: str
    estimated_time: int  # 예상 소요 시간 (초)

    def to_dict(self):
        return {
            'step_number': self.step_number,
            'description': self.description,
            'estimated_time': self.estimated_time
        }


@dataclass
class Recipe:
    """레시피"""
    recipe_id: str
    menu_id: str
    menu_name: str
    ingredients: List[RecipeIngredient] = field(default_factory=list)
    cooking_steps: List[CookingStep] = field(default_factory=list)
    total_cooking_time: int = 0  # 총 조리 시간 (초)
    difficulty: str = "medium"  # easy, medium, hard

    def to_dict(self):
        return {
            'recipe_id': self.recipe_id,
            'menu_id': self.menu_id,
            'menu_name': self.menu_name,
            'ingredients': [ing.to_dict() for ing in self.ingredients],
            'cooking_steps': [step.to_dict() for step in self.cooking_steps],
            'total_cooking_time': self.total_cooking_time,
            'difficulty': self.difficulty
        }

    @staticmethod
    def from_dict(data: dict) -> 'Recipe':
        return Recipe(
            recipe_id=data.get('recipe_id', ''),
            menu_id=data.get('menu_id', ''),
            menu_name=data.get('menu_name', ''),
            ingredients=[],  # 복잡한 변환은 별도 처리
            cooking_steps=[],
            total_cooking_time=data.get('total_cooking_time', 0),
            difficulty=data.get('difficulty', 'medium')
        )


@dataclass
class Supplier:
    """공급업체"""
    supplier_id: str
    name: str
    contact: str
    email: str = ""
    phone: str = ""
    address: str = ""

    def to_dict(self):
        return {
            'supplier_id': self.supplier_id,
            'name': self.name,
            'contact': self.contact,
            'email': self.email,
            'phone': self.phone,
            'address': self.address
        }


@dataclass
class Stock:
    """재고 (3단계 재고 관리 시스템)"""
    stock_id: str
    ingredient: Ingredient
    quantity: float  # 현재 총 수량 (레거시, 호환성 유지)
    threshold: float  # 임계값 (이하로 내려가면 알림)
    supplier: Optional[Supplier] = None
    last_updated: Optional[datetime] = None
    # 3단계 재고 시스템 필드
    stock_area_boxes: int = 0  # 재고 영역의 박스 수
    bed_remaining: int = 0  # 식재료 밧드의 남은 개수 (0~6)
    box_size: int = 6  # 박스당 식재료 개수

    def get_total_quantity(self) -> int:
        """총 재고 개수 계산"""
        return self.stock_area_boxes * self.box_size + self.bed_remaining

    def is_low_stock(self) -> bool:
        """재고 부족 여부"""
        total = self.get_total_quantity()
        return total <= self.threshold

    def to_dict(self):
        return {
            'stock_id': self.stock_id,
            'ingredient': self.ingredient.to_dict(),
            'quantity': self.quantity,  # 레거시
            'threshold': self.threshold,
            'supplier': self.supplier.to_dict() if self.supplier else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'is_low_stock': self.is_low_stock(),
            # 3단계 재고 시스템
            'stock_area_boxes': self.stock_area_boxes,
            'bed_remaining': self.bed_remaining,
            'box_size': self.box_size,
            'total_quantity': self.get_total_quantity()
        }

    @staticmethod
    def from_dict(data: dict) -> 'Stock':
        ingredient_data = data.get('ingredient', {})
        ingredient = Ingredient.from_dict(ingredient_data)

        return Stock(
            stock_id=data.get('stock_id', ''),
            ingredient=ingredient,
            quantity=data.get('quantity', 0.0),
            threshold=data.get('threshold', 0.0),
            supplier=None,  # 별도 처리
            last_updated=None,
            stock_area_boxes=data.get('stock_area_boxes', 0),
            bed_remaining=data.get('bed_remaining', 0),
            box_size=data.get('box_size', 6)
        )


class ServingStatus(Enum):
    """서빙 상태"""
    WAITING = "waiting"          # 대기중
    CALLED = "called"            # 로봇 호출됨
    MOVING = "moving"            # 이동중
    ARRIVED = "arrived"          # 도착
    ERROR = "error"              # 오류
    DELAYED = "delayed"          # 지연
