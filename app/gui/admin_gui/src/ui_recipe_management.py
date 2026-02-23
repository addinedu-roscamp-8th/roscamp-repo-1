"""
레시피 관리
SR-11: 레시피 관리 (CRUD)
"""
import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QApplication, QTableWidgetItem, QMessageBox, QInputDialog,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QSpinBox, QTableWidget, QHeaderView, QFormLayout
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config
from tcp_client import MockAdminServiceClient, AdminServiceClient


class IngredientDialog(QDialog):
    """재료 추가/수정 다이얼로그"""

    def __init__(self, ingredient_data=None, parent=None):
        super().__init__(parent)
        self.ingredient_data = ingredient_data or {}
        self.setup_ui()

    def setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle('재료 추가/수정')
        self.setMinimumSize(400, 200)

        layout = QFormLayout()

        # 재료명
        self.edit_name = QLineEdit()
        self.edit_name.setText(self.ingredient_data.get('ingredient_name', ''))
        layout.addRow('재료명:', self.edit_name)

        # 수량
        self.spin_quantity = QSpinBox()
        self.spin_quantity.setRange(0, 100000)
        self.spin_quantity.setValue(int(self.ingredient_data.get('quantity', 0)))
        layout.addRow('수량:', self.spin_quantity)

        # 단위
        self.edit_unit = QLineEdit()
        self.edit_unit.setText(self.ingredient_data.get('unit', 'g'))
        layout.addRow('단위:', self.edit_unit)

        # 버튼
        button_layout = QHBoxLayout()
        btn_save = QPushButton('저장')
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton('취소')
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_cancel)

        layout.addRow(button_layout)
        self.setLayout(layout)

    def get_data(self):
        """입력된 데이터 반환"""
        return {
            'ingredient_id': self.ingredient_data.get('ingredient_id', f'ING{id(self)}'),
            'ingredient_name': self.edit_name.text(),
            'quantity': self.spin_quantity.value(),
            'unit': self.edit_unit.text()
        }


class CookingStepDialog(QDialog):
    """조리 단계 추가/수정 다이얼로그"""

    def __init__(self, step_data=None, step_number=1, parent=None):
        super().__init__(parent)
        self.step_data = step_data or {}
        self.step_number = step_number
        self.setup_ui()

    def setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle('조리 단계 추가/수정')
        self.setMinimumSize(450, 250)

        layout = QFormLayout()

        # 단계 번호
        self.spin_step_number = QSpinBox()
        self.spin_step_number.setRange(1, 99)
        self.spin_step_number.setValue(self.step_data.get('step_number', self.step_number))
        layout.addRow('단계 번호:', self.spin_step_number)

        # 설명
        self.edit_description = QLineEdit()
        self.edit_description.setText(self.step_data.get('description', ''))
        layout.addRow('설명:', self.edit_description)

        # 예상 시간 (초)
        self.spin_time = QSpinBox()
        self.spin_time.setRange(0, 36000)
        self.spin_time.setValue(self.step_data.get('estimated_time', 60))
        self.spin_time.setSuffix(' 초')
        layout.addRow('예상 시간:', self.spin_time)

        # 버튼
        button_layout = QHBoxLayout()
        btn_save = QPushButton('저장')
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton('취소')
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_cancel)

        layout.addRow(button_layout)
        self.setLayout(layout)

    def get_data(self):
        """입력된 데이터 반환"""
        return {
            'step_number': self.spin_step_number.value(),
            'description': self.edit_description.text(),
            'estimated_time': self.spin_time.value()
        }


class RecipeEditDialog(QDialog):
    """레시피 편집 다이얼로그"""

    def __init__(self, recipe_data, parent=None):
        super().__init__(parent)
        self.recipe_data = recipe_data.copy()
        self.ingredients = list(recipe_data.get('ingredients', []))
        self.cooking_steps = list(recipe_data.get('cooking_steps', []))
        self.setup_ui()

    def setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle('레시피 편집')
        self.setMinimumSize(800, 600)

        main_layout = QVBoxLayout()

        # 기본 정보 섹션
        form_layout = QFormLayout()

        # 메뉴명
        self.edit_menu_name = QLineEdit()
        self.edit_menu_name.setText(self.recipe_data.get('menu_name', ''))
        form_layout.addRow('메뉴명:', self.edit_menu_name)

        # 난이도
        self.combo_difficulty = QComboBox()
        self.combo_difficulty.addItems(['easy', 'medium', 'hard'])
        difficulty_map = {'easy': 0, 'medium': 1, 'hard': 2}
        current_difficulty = self.recipe_data.get('difficulty', 'medium')
        self.combo_difficulty.setCurrentIndex(difficulty_map.get(current_difficulty, 1))
        form_layout.addRow('난이도:', self.combo_difficulty)

        # 총 조리 시간
        self.spin_cooking_time = QSpinBox()
        self.spin_cooking_time.setRange(0, 36000)
        self.spin_cooking_time.setValue(self.recipe_data.get('total_cooking_time', 300))
        self.spin_cooking_time.setSuffix(' 초')
        form_layout.addRow('총 조리 시간:', self.spin_cooking_time)

        main_layout.addLayout(form_layout)

        # 재료 섹션
        main_layout.addWidget(QLabel('<b>재료 목록</b>'))

        self.table_ingredients = QTableWidget()
        self.table_ingredients.setColumnCount(4)
        self.table_ingredients.setHorizontalHeaderLabels(['재료명', '수량', '단위', 'ID'])
        self.table_ingredients.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_ingredients.setColumnWidth(1, 80)
        self.table_ingredients.setColumnWidth(2, 80)
        self.table_ingredients.setColumnHidden(3, True)  # ID 숨김
        self.table_ingredients.setSelectionBehavior(QTableWidget.SelectRows)
        main_layout.addWidget(self.table_ingredients)

        # 재료 버튼
        ingredient_btn_layout = QHBoxLayout()
        btn_add_ingredient = QPushButton('재료 추가')
        btn_add_ingredient.clicked.connect(self.add_ingredient)
        btn_edit_ingredient = QPushButton('재료 수정')
        btn_edit_ingredient.clicked.connect(self.edit_ingredient)
        btn_delete_ingredient = QPushButton('재료 삭제')
        btn_delete_ingredient.clicked.connect(self.delete_ingredient)
        ingredient_btn_layout.addWidget(btn_add_ingredient)
        ingredient_btn_layout.addWidget(btn_edit_ingredient)
        ingredient_btn_layout.addWidget(btn_delete_ingredient)
        ingredient_btn_layout.addStretch()
        main_layout.addLayout(ingredient_btn_layout)

        # 조리 단계 섹션
        main_layout.addWidget(QLabel('<b>조리 단계</b>'))

        self.table_steps = QTableWidget()
        self.table_steps.setColumnCount(3)
        self.table_steps.setHorizontalHeaderLabels(['단계', '설명', '예상 시간(초)'])
        self.table_steps.setColumnWidth(0, 60)
        self.table_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_steps.setColumnWidth(2, 100)
        self.table_steps.setSelectionBehavior(QTableWidget.SelectRows)
        main_layout.addWidget(self.table_steps)

        # 조리 단계 버튼
        step_btn_layout = QHBoxLayout()
        btn_add_step = QPushButton('단계 추가')
        btn_add_step.clicked.connect(self.add_step)
        btn_edit_step = QPushButton('단계 수정')
        btn_edit_step.clicked.connect(self.edit_step)
        btn_delete_step = QPushButton('단계 삭제')
        btn_delete_step.clicked.connect(self.delete_step)
        step_btn_layout.addWidget(btn_add_step)
        step_btn_layout.addWidget(btn_edit_step)
        step_btn_layout.addWidget(btn_delete_step)
        step_btn_layout.addStretch()
        main_layout.addLayout(step_btn_layout)

        # 저장/취소 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        btn_save = QPushButton('저장')
        btn_save.setMinimumSize(100, 40)
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton('취소')
        btn_cancel.setMinimumSize(100, 40)
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_cancel)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # 초기 데이터 로드
        self.load_ingredients()
        self.load_steps()

    def load_ingredients(self):
        """재료 목록 로드"""
        self.table_ingredients.setRowCount(0)
        for ing in self.ingredients:
            row = self.table_ingredients.rowCount()
            self.table_ingredients.insertRow(row)
            self.table_ingredients.setItem(row, 0, QTableWidgetItem(ing.get('ingredient_name', '')))
            self.table_ingredients.setItem(row, 1, QTableWidgetItem(str(ing.get('quantity', 0))))
            self.table_ingredients.setItem(row, 2, QTableWidgetItem(ing.get('unit', '')))
            self.table_ingredients.setItem(row, 3, QTableWidgetItem(ing.get('ingredient_id', '')))

    def load_steps(self):
        """조리 단계 로드"""
        self.table_steps.setRowCount(0)
        for step in self.cooking_steps:
            row = self.table_steps.rowCount()
            self.table_steps.insertRow(row)
            self.table_steps.setItem(row, 0, QTableWidgetItem(str(step.get('step_number', 0))))
            self.table_steps.setItem(row, 1, QTableWidgetItem(step.get('description', '')))
            self.table_steps.setItem(row, 2, QTableWidgetItem(str(step.get('estimated_time', 0))))

    def add_ingredient(self):
        """재료 추가"""
        dialog = IngredientDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            ingredient_data = dialog.get_data()
            self.ingredients.append(ingredient_data)
            self.load_ingredients()

    def edit_ingredient(self):
        """재료 수정"""
        selected_rows = self.table_ingredients.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, '경고', '수정할 재료를 선택하세요.')
            return

        row = selected_rows[0].row()
        ingredient_data = self.ingredients[row]
        dialog = IngredientDialog(ingredient_data, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.ingredients[row] = dialog.get_data()
            self.load_ingredients()

    def delete_ingredient(self):
        """재료 삭제"""
        selected_rows = self.table_ingredients.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, '경고', '삭제할 재료를 선택하세요.')
            return

        row = selected_rows[0].row()
        reply = QMessageBox.question(
            self, '확인', '선택한 재료를 삭제하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.ingredients[row]
            self.load_ingredients()

    def add_step(self):
        """조리 단계 추가"""
        next_step_number = len(self.cooking_steps) + 1
        dialog = CookingStepDialog(step_number=next_step_number, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            step_data = dialog.get_data()
            self.cooking_steps.append(step_data)
            self.load_steps()

    def edit_step(self):
        """조리 단계 수정"""
        selected_rows = self.table_steps.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, '경고', '수정할 단계를 선택하세요.')
            return

        row = selected_rows[0].row()
        step_data = self.cooking_steps[row]
        dialog = CookingStepDialog(step_data, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.cooking_steps[row] = dialog.get_data()
            self.load_steps()

    def delete_step(self):
        """조리 단계 삭제"""
        selected_rows = self.table_steps.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, '경고', '삭제할 단계를 선택하세요.')
            return

        row = selected_rows[0].row()
        reply = QMessageBox.question(
            self, '확인', '선택한 단계를 삭제하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.cooking_steps[row]
            # 단계 번호 재정렬
            for i, step in enumerate(self.cooking_steps):
                step['step_number'] = i + 1
            self.load_steps()

    def get_recipe_data(self):
        """수정된 레시피 데이터 반환"""
        return {
            **self.recipe_data,
            'menu_name': self.edit_menu_name.text(),
            'difficulty': self.combo_difficulty.currentText(),
            'total_cooking_time': self.spin_cooking_time.value(),
            'ingredients': self.ingredients,
            'cooking_steps': self.cooking_steps
        }


class RecipeManagementWidget(QWidget):
    """레시피 관리 위젯"""

    def __init__(self, use_mock=True):
        super().__init__()
        self.use_mock = use_mock
        self.selected_recipe_id = None
        self.recipes_data = []

        # TCP 클라이언트 초기화
        if use_mock:
            self.client = MockAdminServiceClient()
        else:
            self.client = AdminServiceClient()

        self.setup_ui()
        self.connect_signals()
        self.connect_to_server()

        # 초기 데이터 로드
        self.load_recipes()

    def setup_ui(self):
        """UI 초기화"""
        ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'recipe_management.ui')
        loadUi(ui_path, self)

        # 테이블 컬럼 너비 설정
        self.table_recipes.setColumnWidth(0, 120)  # 레시피 ID
        self.table_recipes.setColumnWidth(1, 250)  # 메뉴명
        self.table_recipes.setColumnWidth(2, 120)  # 조리 시간
        self.table_recipes.setColumnWidth(3, 100)  # 난이도
        self.table_recipes.setColumnWidth(4, 100)  # 재료 수

    def connect_signals(self):
        """시그널 연결"""
        self.btn_add_recipe.clicked.connect(self.add_recipe)
        self.btn_edit_recipe.clicked.connect(self.edit_recipe)
        self.btn_delete_recipe.clicked.connect(self.delete_recipe)
        self.btn_refresh.clicked.connect(self.load_recipes)

        # 테이블 선택 변경
        self.table_recipes.itemSelectionChanged.connect(self.on_selection_changed)

    def connect_to_server(self):
        """서버 연결"""
        if self.client.connect():
            print('[RecipeManagement] 서버 연결 성공')
        else:
            print('[RecipeManagement] 서버 연결 실패')

    def load_recipes(self):
        """레시피 목록 로드"""
        recipes = self.client.get_recipes()
        self.recipes_data = recipes
        self.display_recipes(recipes)

    def display_recipes(self, recipes):
        """레시피 목록 표시"""
        self.table_recipes.setRowCount(0)

        for recipe in recipes:
            row = self.table_recipes.rowCount()
            self.table_recipes.insertRow(row)

            # 레시피 ID
            self.table_recipes.setItem(row, 0, QTableWidgetItem(recipe['recipe_id']))

            # 메뉴명
            self.table_recipes.setItem(row, 1, QTableWidgetItem(recipe['menu_name']))

            # 조리 시간
            cooking_time = recipe.get('total_cooking_time', 0)
            minutes = cooking_time // 60
            self.table_recipes.setItem(row, 2, QTableWidgetItem(f'{minutes}분'))

            # 난이도
            difficulty = recipe.get('difficulty', 'medium')
            difficulty_map = {'easy': '쉬움', 'medium': '보통', 'hard': '어려움'}
            self.table_recipes.setItem(row, 3, QTableWidgetItem(difficulty_map.get(difficulty, difficulty)))

            # 재료 수
            ingredients_count = len(recipe.get('ingredients', []))
            self.table_recipes.setItem(row, 4, QTableWidgetItem(f'{ingredients_count}개'))

    def on_selection_changed(self):
        """테이블 선택 변경 시"""
        selected_rows = self.table_recipes.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            recipe_id_item = self.table_recipes.item(row, 0)
            if recipe_id_item:
                self.selected_recipe_id = recipe_id_item.text()

                # 레시피 상세 정보 표시
                recipe = next((r for r in self.recipes_data if r['recipe_id'] == self.selected_recipe_id), None)
                if recipe:
                    self.display_recipe_detail(recipe)

                # 버튼 활성화
                self.btn_edit_recipe.setEnabled(True)
                self.btn_delete_recipe.setEnabled(True)
        else:
            self.selected_recipe_id = None
            self.text_recipe_detail.clear()
            self.btn_edit_recipe.setEnabled(False)
            self.btn_delete_recipe.setEnabled(False)

    def display_recipe_detail(self, recipe):
        """레시피 상세 정보 표시"""
        # 재료 리스트
        ingredients_text = '\n'.join([
            f"  - {ing['ingredient_name']}: {ing['quantity']}{ing['unit']}"
            for ing in recipe.get('ingredients', [])
        ])

        # 조리 단계
        steps_text = '\n'.join([
            f"  {step['step_number']}. {step['description']} ({step['estimated_time']}초)"
            for step in recipe.get('cooking_steps', [])
        ])

        detail_text = f"""
메뉴명: {recipe['menu_name']}
레시피 ID: {recipe['recipe_id']}
메뉴 ID: {recipe['menu_id']}
난이도: {recipe.get('difficulty', 'medium')}
총 조리 시간: {recipe.get('total_cooking_time', 0)}초

[재료]
{ingredients_text if ingredients_text else '  (재료 정보 없음)'}

[조리 단계]
{steps_text if steps_text else '  (조리 단계 정보 없음)'}
        """

        self.text_recipe_detail.setText(detail_text.strip())

    def add_recipe(self):
        """레시피 추가"""
        # 간단한 다이얼로그로 메뉴명 입력
        menu_name, ok = QInputDialog.getText(self, '레시피 추가', '메뉴명을 입력하세요:')

        if ok and menu_name:
            # 새 레시피 데이터 생성
            new_recipe_id = f'R{len(self.recipes_data) + 1:03d}'
            new_menu_id = f'M{len(self.recipes_data) + 1:03d}'

            recipe_data = {
                'recipe_id': new_recipe_id,
                'menu_id': new_menu_id,
                'menu_name': menu_name,
                'ingredients': [],
                'cooking_steps': [],
                'total_cooking_time': 300,
                'difficulty': 'medium'
            }

            if self.client.create_recipe(recipe_data):
                QMessageBox.information(self, '성공', f'레시피 "{menu_name}"이(가) 추가되었습니다.')
                self.load_recipes()
            else:
                QMessageBox.warning(self, '실패', '레시피 추가에 실패했습니다.')

    def edit_recipe(self):
        """레시피 수정"""
        if not self.selected_recipe_id:
            return

        # 현재 레시피 정보 가져오기
        recipe = next((r for r in self.recipes_data if r['recipe_id'] == self.selected_recipe_id), None)
        if not recipe:
            return

        # 레시피 편집 다이얼로그 표시
        dialog = RecipeEditDialog(recipe, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            recipe_data = dialog.get_recipe_data()

            if self.client.update_recipe(self.selected_recipe_id, recipe_data):
                QMessageBox.information(self, '성공', '레시피가 수정되었습니다.')
                self.load_recipes()
            else:
                QMessageBox.warning(self, '실패', '레시피 수정에 실패했습니다.')

    def delete_recipe(self):
        """레시피 삭제"""
        if not self.selected_recipe_id:
            return

        recipe = next((r for r in self.recipes_data if r['recipe_id'] == self.selected_recipe_id), None)
        if not recipe:
            return

        reply = QMessageBox.question(
            self, '확인', f'레시피 "{recipe["menu_name"]}"을(를) 삭제하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.client.delete_recipe(self.selected_recipe_id):
                QMessageBox.information(self, '성공', '레시피가 삭제되었습니다.')
                self.load_recipes()
            else:
                QMessageBox.warning(self, '실패', '레시피 삭제에 실패했습니다.')

    def closeEvent(self, event):
        """위젯 종료 시"""
        self.client.disconnect()
        event.accept()


# 테스트 코드
if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = RecipeManagementWidget(use_mock=True)
    window.show()

    sys.exit(app.exec_())
