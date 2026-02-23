from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models import StoreMenuRecipeBom, StoreIngredientMst
from sqlalchemy import desc

bp = Blueprint('menu_recipe', __name__, url_prefix='/menu-recipe')


@bp.route('/<menu_sku>', methods=['GET'])
def get_menu_recipe(menu_sku):
    """
    메뉴 레시피 조회
    ---
    tags:
      - Menu Recipe
    parameters:
      - in: path
        name: menu_sku
        type: string
        required: true
        description: 메뉴 SKU
    responses:
      200:
        description: 메뉴 레시피 정보
        schema:
          type: object
          properties:
            menu_sku:
              type: string
            recipe:
              type: array
              items:
                type: object
                properties:
                  ingredient_sku:
                    type: string
                  ingredient_name:
                    type: string
                  qty_per_menu:
                    type: number
                  unit:
                    type: string
      404:
        description: 레시피를 찾을 수 없음
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        # BOM 조회
        bom_items = db.query(StoreMenuRecipeBom).filter(
            StoreMenuRecipeBom.menu_sku == menu_sku
        ).all()
        
        if not bom_items:
            return jsonify({
                'menu_sku': menu_sku,
                'recipe': []
            })
        
        # 원재료 정보 조인
        recipe = []
        for bom in bom_items:
            ingredient = db.query(StoreIngredientMst).filter(
                StoreIngredientMst.ingredient_sku == bom.ingredient_sku
            ).first()
            
            recipe.append({
                'ingredient_sku': bom.ingredient_sku,
                'ingredient_name': ingredient.ingredient_name if ingredient else bom.ingredient_sku,
                'qty_per_menu': float(bom.qty_per_menu),
                'unit': ingredient.base_unit if ingredient else 'g'
            })
        
        return jsonify({
            'menu_sku': menu_sku,
            'recipe': recipe
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('', methods=['POST'])
def create_or_update_recipe():
    """
    메뉴 레시피 생성/업데이트
    ---
    tags:
      - Menu Recipe
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - menu_sku
            - recipe
          properties:
            menu_sku:
              type: string
              description: "메뉴 SKU"
            recipe:
              type: array
              description: "레시피 항목 목록"
              items:
                type: object
                required:
                  - ingredient_sku
                  - qty_per_menu
                properties:
                  ingredient_sku:
                    type: string
                  qty_per_menu:
                    type: number
    responses:
      200:
        description: 레시피가 생성/업데이트되었습니다
      400:
        description: 잘못된 요청
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    if 'menu_sku' not in data:
        return jsonify({'error': 'Missing required field: menu_sku'}), 400
    
    if 'recipe' not in data or not isinstance(data['recipe'], list):
        return jsonify({'error': 'Missing or invalid recipe field. Must be an array'}), 400
    
    db = get_db()
    try:
        menu_sku = data['menu_sku']
        
        # 기존 레시피 삭제
        db.query(StoreMenuRecipeBom).filter(
            StoreMenuRecipeBom.menu_sku == menu_sku
        ).delete()
        
        # 새 레시피 추가
        for item in data['recipe']:
            if 'ingredient_sku' not in item or 'qty_per_menu' not in item:
                continue
            
            # 원재료 존재 확인
            ingredient = db.query(StoreIngredientMst).filter(
                StoreIngredientMst.ingredient_sku == item['ingredient_sku']
            ).first()
            
            if not ingredient:
                return jsonify({
                    'error': f'Ingredient not found: {item["ingredient_sku"]}'
                }), 400
            
            bom = StoreMenuRecipeBom(
                menu_sku=menu_sku,
                ingredient_sku=item['ingredient_sku'],
                qty_per_menu=float(item['qty_per_menu'])
            )
            
            db.add(bom)
        
        db.commit()
        
        return jsonify({
            'success': True,
            'menu_sku': menu_sku,
            'recipe_count': len(data['recipe'])
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<menu_sku>/<ingredient_sku>', methods=['DELETE'])
def delete_recipe_item(menu_sku, ingredient_sku):
    """
    레시피 항목 삭제
    ---
    tags:
      - Menu Recipe
    parameters:
      - in: path
        name: menu_sku
        type: string
        required: true
      - in: path
        name: ingredient_sku
        type: string
        required: true
    responses:
      200:
        description: 레시피 항목이 삭제되었습니다
      404:
        description: 레시피 항목을 찾을 수 없음
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        bom = db.query(StoreMenuRecipeBom).filter(
            StoreMenuRecipeBom.menu_sku == menu_sku,
            StoreMenuRecipeBom.ingredient_sku == ingredient_sku
        ).first()
        
        if not bom:
            return jsonify({'error': 'Recipe item not found'}), 404
        
        db.delete(bom)
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Recipe item deleted'
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<menu_sku>', methods=['DELETE'])
def delete_menu_recipe(menu_sku):
    """
    메뉴 레시피 전체 삭제
    ---
    tags:
      - Menu Recipe
    parameters:
      - in: path
        name: menu_sku
        type: string
        required: true
    responses:
      200:
        description: 레시피가 삭제되었습니다
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        deleted = db.query(StoreMenuRecipeBom).filter(
            StoreMenuRecipeBom.menu_sku == menu_sku
        ).delete()
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Menu recipe deleted',
            'deleted_count': deleted
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/list', methods=['GET'])
def list_all_recipes():
    """
    모든 메뉴 레시피 목록 조회
    ---
    tags:
      - Menu Recipe
    parameters:
      - in: query
        name: limit
        type: integer
        default: 50
      - in: query
        name: offset
        type: integer
        default: 0
    responses:
      200:
        description: 메뉴 레시피 목록
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        # 메뉴 SKU별로 그룹화
        from sqlalchemy import func
        
        menu_skus = db.query(
            StoreMenuRecipeBom.menu_sku,
            func.count(StoreMenuRecipeBom.ingredient_sku).label('ingredient_count')
        ).group_by(StoreMenuRecipeBom.menu_sku).all()
        
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        total = len(menu_skus)
        paginated_skus = menu_skus[offset:offset+limit]
        
        recipes = []
        for menu_sku, ingredient_count in paginated_skus:
            recipes.append({
                'menu_sku': menu_sku,
                'ingredient_count': ingredient_count
            })
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'recipes': recipes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

