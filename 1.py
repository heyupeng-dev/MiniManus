"""测试导入 pydantic、fastapi、openai、uvicorn"""

import openai
from pydantic import BaseModel
from fastapi import FastAPI

# 测试 pydantic
class Item(BaseModel):
    name: str
    price: float

# 测试 fastapi
app = FastAPI()

# 测试 openai
client = openai.OpenAI(api_key="sk-test")

# 测试 uvicorn
import uvicorn


@app.get("/")
def read_root():
    return {"message": "所有导入成功"}


if __name__ == "__main__":
    item = Item(name="test", price=9.99)
    print(f"Pydantic OK: {item}")
    print(f"FastAPI OK: {app.title}")
    print(f"OpenAI OK: {client.api_key[:5]}...")
    print("所有导入测试通过！")
    uvicorn.run(app, host="127.0.0.1", port=8000)
