from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core.function_calling import run_test_function, list_registered_functions

router = APIRouter(prefix="/functions", tags=["Function calling"])


class FunctionCallRequest(BaseModel):
    function_name: str = Field(..., description="호출할 함수 이름 (예: test_voice_order)")
    arguments: dict | None = Field(default=None, description="함수 인자")


@router.post(
    "/call",
    summary="함수 호출",
    description="등록된 함수를 호출합니다. 테스트 함수는 로그로 동작 여부 확인.",
)
async def post_function_call(body: FunctionCallRequest) -> dict:
    try:
        result = run_test_function(body.function_name, arguments=body.arguments or {})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/list",
    summary="등록된 함수 목록",
    description="호출 가능한 함수 목록 및 스키마.",
)
async def get_functions_list() -> dict:
    return {"functions": list_registered_functions()}
