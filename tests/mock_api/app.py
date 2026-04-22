from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse


def create_app() -> FastAPI:
    app = FastAPI()
    store = MockStore()

    @app.get("/_health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "test_case_mock_api",
            "version": "1",
            "config_signature": store.config_signature,
        }

    @app.get("/get")
    async def httpbin_get(request: Request) -> dict[str, Any]:
        return httpbin_payload(request, args=dict(request.query_params))

    @app.api_route("/anything", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @app.api_route("/anything/{rest_of_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def httpbin_anything(request: Request, rest_of_path: str = "") -> dict[str, Any]:
        payload = httpbin_payload(request, args=dict(request.query_params))
        payload["method"] = request.method
        if rest_of_path:
            payload["url"] = str(request.url)
        return payload

    @app.post("/post")
    @app.put("/put")
    @app.patch("/patch")
    @app.delete("/delete")
    async def httpbin_write(request: Request) -> dict[str, Any]:
        data = await request.json()
        payload = httpbin_payload(request, args=dict(request.query_params))
        payload["json"] = data
        return payload

    @app.get("/basic-auth/{user}/{passwd}")
    async def httpbin_basic_auth(user: str, passwd: str, request: Request) -> Response:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return Response(status_code=401)
        try:
            decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
        except Exception:
            return Response(status_code=401)
        username, password = decoded.split(":", 1)
        if username != user or password != passwd:
            return Response(status_code=401)
        return JSONResponse({"authenticated": True, "user": user})

    @app.get("/status/{code}")
    async def httpbin_status(code: int) -> Response:
        if code == 418:
            return PlainTextResponse("I'm a teapot", status_code=418)
        return Response(status_code=code)

    @app.get("/headers")
    async def httpbin_headers(request: Request) -> dict[str, Any]:
        return {"headers": normalized_headers(request)}

    @app.get("/user-agent")
    async def httpbin_user_agent(request: Request) -> dict[str, Any]:
        return {"user-agent": request.headers.get("user-agent", "")}

    @app.get("/uuid")
    async def httpbin_uuid() -> dict[str, str]:
        return {"uuid": str(uuid.uuid4())}

    @app.get("/ip")
    async def httpbin_ip() -> dict[str, str]:
        return {"origin": "127.0.0.1"}

    @app.get("/response-headers")
    async def httpbin_response_headers(request: Request) -> Response:
        params = dict(request.query_params)
        return JSONResponse(params, headers=params)

    @app.get("/delay/{seconds}")
    async def httpbin_delay(seconds: int, request: Request) -> dict[str, Any]:
        await asyncio.sleep(seconds)
        return httpbin_payload(request, args=dict(request.query_params))

    @app.get("/gzip")
    async def httpbin_gzip(request: Request) -> dict[str, Any]:
        return {
            "gzipped": True,
            "method": request.method,
            "headers": normalized_headers(request),
            "origin": "127.0.0.1",
        }

    @app.get("/deflate")
    async def httpbin_deflate(request: Request) -> dict[str, Any]:
        return {
            "deflated": True,
            "method": request.method,
            "headers": normalized_headers(request),
            "origin": "127.0.0.1",
        }

    @app.get("/cookies")
    async def httpbin_cookies(request: Request) -> dict[str, Any]:
        return {"cookies": dict(request.cookies)}

    @app.get("/cookies/set")
    async def httpbin_cookies_set(request: Request) -> Response:
        params = dict(request.query_params)
        response = JSONResponse({"cookies": params})
        for key, value in params.items():
            response.set_cookie(key, value)
        return response

    @app.get("/cookies/delete")
    async def httpbin_cookies_delete(request: Request) -> Response:
        query_pairs = parse_qsl(request.url.query, keep_blank_values=True)
        response = JSONResponse({"cookies": {}})
        for key, _ in query_pairs:
            response.delete_cookie(key)
        return response

    @app.get("/redirect-to")
    async def httpbin_redirect_to(url: str) -> Response:
        return RedirectResponse(url=url, status_code=302)

    @app.get("/jsonplaceholder/posts")
    async def jsonplaceholder_posts(userId: int | None = None) -> list[dict[str, Any]]:
        posts = store.jsonplaceholder_posts
        if userId is not None:
            posts = [post for post in posts if post["userId"] == userId]
        return posts

    @app.get("/jsonplaceholder/posts/{post_id}")
    async def jsonplaceholder_post(post_id: int) -> dict[str, Any]:
        return store.get_by_id(store.jsonplaceholder_posts, post_id)

    @app.get("/jsonplaceholder/posts/{post_id}/comments")
    async def jsonplaceholder_post_comments(post_id: int) -> list[dict[str, Any]]:
        return [item for item in store.jsonplaceholder_comments if item["postId"] == post_id]

    @app.post("/jsonplaceholder/posts")
    async def jsonplaceholder_create_post(request: Request) -> Response:
        payload = await request.json()
        payload["id"] = 101
        return JSONResponse(payload, status_code=201)

    @app.put("/jsonplaceholder/posts/{post_id}")
    async def jsonplaceholder_replace_post(post_id: int, request: Request) -> dict[str, Any]:
        payload = await request.json()
        payload["id"] = post_id
        return payload

    @app.patch("/jsonplaceholder/posts/{post_id}")
    async def jsonplaceholder_patch_post(post_id: int, request: Request) -> dict[str, Any]:
        payload = await request.json()
        base = deepcopy(store.get_by_id(store.jsonplaceholder_posts, post_id))
        base.update(payload)
        return base

    @app.delete("/jsonplaceholder/posts/{post_id}")
    async def jsonplaceholder_delete_post(post_id: int) -> dict[str, Any]:
        return {}

    @app.get("/jsonplaceholder/comments")
    async def jsonplaceholder_comments(postId: int | None = None) -> list[dict[str, Any]]:
        items = store.jsonplaceholder_comments
        if postId is not None:
            items = [item for item in items if item["postId"] == postId]
        return items

    @app.get("/jsonplaceholder/comments/{comment_id}")
    async def jsonplaceholder_comment(comment_id: int) -> dict[str, Any]:
        return store.get_by_id(store.jsonplaceholder_comments, comment_id)

    @app.get("/jsonplaceholder/albums")
    async def jsonplaceholder_albums(userId: int | None = None) -> list[dict[str, Any]]:
        items = store.jsonplaceholder_albums
        if userId is not None:
            items = [item for item in items if item["userId"] == userId]
        return items

    @app.get("/jsonplaceholder/albums/{album_id}")
    async def jsonplaceholder_album(album_id: int) -> dict[str, Any]:
        return store.get_by_id(store.jsonplaceholder_albums, album_id)

    @app.get("/jsonplaceholder/albums/{album_id}/photos")
    async def jsonplaceholder_album_photos(album_id: int) -> list[dict[str, Any]]:
        return [item for item in store.jsonplaceholder_photos if item["albumId"] == album_id]

    @app.get("/jsonplaceholder/photos")
    async def jsonplaceholder_photos(albumId: int | None = None) -> list[dict[str, Any]]:
        items = store.jsonplaceholder_photos
        if albumId is not None:
            items = [item for item in items if item["albumId"] == albumId]
        return items

    @app.get("/jsonplaceholder/photos/{photo_id}")
    async def jsonplaceholder_photo(photo_id: int) -> dict[str, Any]:
        return store.get_by_id(store.jsonplaceholder_photos, photo_id)

    @app.get("/jsonplaceholder/todos")
    async def jsonplaceholder_todos(userId: int | None = None) -> list[dict[str, Any]]:
        items = store.jsonplaceholder_todos
        if userId is not None:
            items = [item for item in items if item["userId"] == userId]
        return items

    @app.get("/jsonplaceholder/todos/{todo_id}")
    async def jsonplaceholder_todo(todo_id: int) -> dict[str, Any]:
        return store.get_by_id(store.jsonplaceholder_todos, todo_id)

    @app.get("/jsonplaceholder/users")
    async def jsonplaceholder_users() -> list[dict[str, Any]]:
        return store.jsonplaceholder_users

    @app.get("/jsonplaceholder/users/{user_id}")
    async def jsonplaceholder_user(user_id: int) -> dict[str, Any]:
        return store.get_by_id(store.jsonplaceholder_users, user_id)

    @app.get("/jsonplaceholder/users/{user_id}/posts")
    async def jsonplaceholder_user_posts(user_id: int) -> list[dict[str, Any]]:
        return [item for item in store.jsonplaceholder_posts if item["userId"] == user_id]

    @app.get("/jsonplaceholder/users/{user_id}/todos")
    async def jsonplaceholder_user_todos(user_id: int) -> list[dict[str, Any]]:
        return [item for item in store.jsonplaceholder_todos if item["userId"] == user_id]

    @app.get("/jsonplaceholder/users/{user_id}/albums")
    async def jsonplaceholder_user_albums(user_id: int) -> list[dict[str, Any]]:
        return [item for item in store.jsonplaceholder_albums if item["userId"] == user_id]

    @app.get("/dummyjson/test")
    async def dummy_test(request: Request) -> dict[str, Any]:
        delay = request.query_params.get("delay")
        if delay:
            await asyncio.sleep(int(delay) / 1000)
        return {"status": "ok", "method": request.method}

    @app.get("/dummyjson/ip")
    async def dummy_ip(request: Request) -> dict[str, Any]:
        return {"ip": "127.0.0.1", "userAgent": request.headers.get("user-agent", "")}

    @app.get("/dummyjson/products")
    async def dummy_products(
        q: str | None = None,
        limit: int | None = None,
        skip: int | None = None,
        select: list[str] | None = None,
        sortBy: str | None = None,
        order: str | None = None,
    ) -> dict[str, Any]:
        items = deepcopy(store.dummy_products)
        if q:
            items = [item for item in items if q.lower() in item["title"].lower()]
        if sortBy:
            items = sorted(items, key=lambda item: item.get(sortBy), reverse=order == "desc")
        total = len(items)
        page = paginate(items, limit, skip)
        if select:
            page = [{key: item[key] for key in select if key in item} for item in page]
        return list_payload("products", page, total, skip, limit)

    @app.get("/dummyjson/products/search")
    async def dummy_products_search(q: str) -> dict[str, Any]:
        items = [item for item in deepcopy(store.dummy_products) if q.lower() in item["title"].lower()]
        return list_payload("products", items, len(items), 0, len(items))

    @app.get("/dummyjson/products/1")
    async def dummy_product_1() -> dict[str, Any]:
        return deepcopy(store.dummy_products[0])

    @app.get("/dummyjson/products/category-list")
    async def dummy_product_category_list() -> list[str]:
        return store.dummy_product_categories

    @app.get("/dummyjson/products/category/{category}")
    async def dummy_products_by_category(category: str) -> dict[str, Any]:
        items = [item for item in store.dummy_products if item["category"] == category]
        return list_payload("products", items, len(items), 0, len(items))

    @app.get("/dummyjson/products/{product_id}")
    async def dummy_product(product_id: int) -> dict[str, Any]:
        return deepcopy(store.get_by_id(store.dummy_products, product_id))

    @app.post("/dummyjson/products/add")
    async def dummy_products_add(request: Request) -> Response:
        payload = await request.json()
        payload["id"] = 194
        return JSONResponse(payload, status_code=201)

    @app.put("/dummyjson/products/{product_id}")
    async def dummy_products_update(product_id: int, request: Request) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_products, product_id))
        base.update(await request.json())
        return base

    @app.delete("/dummyjson/products/{product_id}")
    async def dummy_products_delete(product_id: int) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_products, product_id))
        base["isDeleted"] = True
        base["deletedOn"] = "2026-04-22T00:00:00.000Z"
        return base

    @app.get("/dummyjson/users")
    async def dummy_users(
        q: str | None = None,
        limit: int | None = None,
        skip: int | None = None,
        select: list[str] | None = None,
    ) -> dict[str, Any]:
        items = deepcopy(store.dummy_users)
        if q:
            items = [item for item in items if q.lower() in item["firstName"].lower()]
        total = len(items)
        page = paginate(items, limit, skip)
        if select:
            page = [{key: item[key] for key in select if key in item} for item in page]
        return list_payload("users", page, total, skip, limit)

    @app.get("/dummyjson/users/search")
    async def dummy_users_search(q: str) -> dict[str, Any]:
        items = [item for item in deepcopy(store.dummy_users) if q.lower() in item["firstName"].lower()]
        return list_payload("users", items, len(items), 0, len(items))

    @app.get("/dummyjson/users/filter")
    async def dummy_users_filter(key: str, value: str) -> dict[str, Any]:
        if key == "hair.color":
            items = [item for item in store.dummy_users if item["hair"]["color"] == value]
        else:
            items = []
        return list_payload("users", items, len(items), 0, len(items))

    @app.get("/dummyjson/users/{user_id}")
    async def dummy_user(user_id: int) -> dict[str, Any]:
        return deepcopy(store.get_by_id(store.dummy_users, user_id))

    @app.get("/dummyjson/users/{user_id}/posts")
    async def dummy_user_posts(user_id: int) -> dict[str, Any]:
        items = [item for item in store.dummy_posts if item["userId"] == user_id]
        return list_payload("posts", items, len(items), 0, len(items))

    @app.get("/dummyjson/users/{user_id}/todos")
    async def dummy_user_todos(user_id: int) -> dict[str, Any]:
        items = [item for item in store.dummy_todos if item["userId"] == user_id]
        return list_payload("todos", items, len(items), 0, len(items))

    @app.post("/dummyjson/users/add")
    async def dummy_users_add(request: Request) -> Response:
        payload = await request.json()
        payload["id"] = 31
        return JSONResponse(payload, status_code=201)

    @app.put("/dummyjson/users/{user_id}")
    async def dummy_users_update(user_id: int, request: Request) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_users, user_id))
        base.update(await request.json())
        return base

    @app.delete("/dummyjson/users/{user_id}")
    async def dummy_users_delete(user_id: int) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_users, user_id))
        base["isDeleted"] = True
        base["deletedOn"] = "2026-04-22T00:00:00.000Z"
        return base

    @app.get("/dummyjson/posts")
    async def dummy_posts(q: str | None = None) -> dict[str, Any]:
        items = deepcopy(store.dummy_posts)
        if q:
            items = [item for item in items if q.lower() in item["title"].lower()]
        return list_payload("posts", items, len(items), 0, len(items))

    @app.get("/dummyjson/posts/search")
    async def dummy_posts_search(q: str) -> dict[str, Any]:
        items = [item for item in deepcopy(store.dummy_posts) if q.lower() in item["title"].lower()]
        return list_payload("posts", items, len(items), 0, len(items))

    @app.get("/dummyjson/posts/{post_id}")
    async def dummy_post(post_id: int) -> dict[str, Any]:
        return deepcopy(store.get_by_id(store.dummy_posts, post_id))

    @app.get("/dummyjson/posts/user/{user_id}")
    async def dummy_posts_by_user(user_id: int) -> dict[str, Any]:
        items = [item for item in store.dummy_posts if item["userId"] == user_id]
        return list_payload("posts", items, len(items), 0, len(items))

    @app.get("/dummyjson/posts/{post_id}/comments")
    async def dummy_post_comments(post_id: int) -> dict[str, Any]:
        items = [item for item in store.dummy_comments if item["postId"] == post_id]
        return list_payload("comments", items, len(items), 0, len(items))

    @app.post("/dummyjson/posts/add")
    async def dummy_posts_add(request: Request) -> Response:
        payload = await request.json()
        payload["id"] = 252
        return JSONResponse(payload, status_code=201)

    @app.put("/dummyjson/posts/{post_id}")
    async def dummy_posts_update(post_id: int, request: Request) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_posts, post_id))
        base.update(await request.json())
        return base

    @app.delete("/dummyjson/posts/{post_id}")
    async def dummy_posts_delete(post_id: int) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_posts, post_id))
        base["isDeleted"] = True
        base["deletedOn"] = "2026-04-22T00:00:00.000Z"
        return base

    @app.get("/dummyjson/comments")
    async def dummy_comments(limit: int | None = None, skip: int | None = None) -> dict[str, Any]:
        items = deepcopy(store.dummy_comments)
        total = len(items)
        page = paginate(items, limit, skip)
        return list_payload("comments", page, total, skip, limit)

    @app.get("/dummyjson/comments/{comment_id}")
    async def dummy_comment(comment_id: int) -> dict[str, Any]:
        return deepcopy(store.get_by_id(store.dummy_comments, comment_id))

    @app.get("/dummyjson/comments/post/{post_id}")
    async def dummy_comments_post(post_id: int) -> dict[str, Any]:
        items = [item for item in store.dummy_comments if item["postId"] == post_id]
        return list_payload("comments", items, len(items), 0, len(items))

    @app.post("/dummyjson/comments/add")
    async def dummy_comments_add(request: Request) -> Response:
        payload = await request.json()
        payload["id"] = 341
        payload["user"] = {"id": payload.get("userId", 5), "username": "jdoe", "fullName": "Jane Doe"}
        return JSONResponse(payload, status_code=201)

    @app.put("/dummyjson/comments/{comment_id}")
    async def dummy_comments_update(comment_id: int, request: Request) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_comments, comment_id))
        base.update(await request.json())
        return base

    @app.delete("/dummyjson/comments/{comment_id}")
    async def dummy_comments_delete(comment_id: int) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_comments, comment_id))
        base["isDeleted"] = True
        base["deletedOn"] = "2026-04-22T00:00:00.000Z"
        return base

    @app.get("/dummyjson/todos")
    async def dummy_todos(limit: int | None = None, skip: int | None = None) -> dict[str, Any]:
        items = deepcopy(store.dummy_todos)
        total = len(items)
        page = paginate(items, limit, skip)
        return list_payload("todos", page, total, skip, limit)

    @app.get("/dummyjson/todos/{todo_id}")
    async def dummy_todo(todo_id: int) -> dict[str, Any]:
        return deepcopy(store.get_by_id(store.dummy_todos, todo_id))

    @app.get("/dummyjson/todos/user/{user_id}")
    async def dummy_todos_user(user_id: int) -> dict[str, Any]:
        items = [item for item in store.dummy_todos if item["userId"] == user_id]
        return list_payload("todos", items, len(items), 0, len(items))

    @app.post("/dummyjson/todos/add")
    async def dummy_todos_add(request: Request) -> Response:
        payload = await request.json()
        payload["id"] = 151
        return JSONResponse(payload, status_code=201)

    @app.put("/dummyjson/todos/{todo_id}")
    async def dummy_todos_update(todo_id: int, request: Request) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_todos, todo_id))
        base.update(await request.json())
        return base

    @app.delete("/dummyjson/todos/{todo_id}")
    async def dummy_todos_delete(todo_id: int) -> dict[str, Any]:
        base = deepcopy(store.get_by_id(store.dummy_todos, todo_id))
        base["isDeleted"] = True
        base["deletedOn"] = "2026-04-22T00:00:00.000Z"
        return base

    @app.get("/dummyjson/quotes")
    async def dummy_quotes(limit: int | None = None, skip: int | None = None) -> dict[str, Any]:
        items = deepcopy(store.dummy_quotes)
        total = len(items)
        page = paginate(items, limit, skip)
        return list_payload("quotes", page, total, skip, limit)

    @app.get("/dummyjson/quotes/{quote_id}")
    async def dummy_quote(quote_id: int) -> dict[str, Any]:
        return deepcopy(store.get_by_id(store.dummy_quotes, quote_id))

    @app.post("/dummyjson/auth/login")
    async def dummy_auth_login(request: Request) -> Response:
        payload = await request.json()
        if payload.get("username") != store.auth_username or payload.get("password") != store.auth_password:
            return JSONResponse({"message": "Invalid credentials"}, status_code=400)
        response = JSONResponse(store.dummy_login_payload)
        response.set_cookie("accessToken", store.access_token)
        response.set_cookie("refreshToken", store.refresh_token)
        return response

    @app.get("/dummyjson/auth/me")
    async def dummy_auth_me(request: Request) -> Response:
        token = bearer_token(request)
        if token not in {store.access_token, store.refreshed_access_token}:
            return JSONResponse({"message": "Invalid/Expired Token!"}, status_code=401)
        return JSONResponse(store.dummy_auth_me_payload)

    @app.post("/dummyjson/auth/refresh")
    async def dummy_auth_refresh(request: Request) -> Response:
        payload = await request.json()
        if payload.get("refreshToken") != store.refresh_token:
            return JSONResponse({"message": "Invalid/Expired Token!"}, status_code=401)
        return JSONResponse(
            {
                "accessToken": store.refreshed_access_token,
                "refreshToken": store.refreshed_refresh_token,
            }
        )

    return app


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.split(" ", 1)[1]
    return None


def httpbin_payload(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "args": args,
        "headers": normalized_headers(request),
        "url": str(request.url),
    }


def normalized_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        name = "-".join(part.capitalize() for part in key.split("-"))
        headers[name] = value
    return headers


def list_payload(name: str, items: list[dict[str, Any]] | list[str], total: int, skip: int | None, limit: int | None) -> dict[str, Any]:
    actual_skip = 0 if skip is None else skip
    actual_limit = total if limit is None else limit
    return {
        name: items,
        "total": total,
        "skip": actual_skip,
        "limit": actual_limit,
    }


def paginate(items: list[dict[str, Any]], limit: int | None, skip: int | None) -> list[dict[str, Any]]:
    actual_skip = 0 if skip is None else skip
    if limit is None:
        return items[actual_skip:]
    return items[actual_skip : actual_skip + limit]


@dataclass
class MockStore:
    access_token: str = "header.payload.signature"
    refresh_token: str = "refresh.payload.signature"
    refreshed_access_token: str = "newheader.newpayload.newsignature"
    refreshed_refresh_token: str = "newrefresh.payload.signature"
    auth_username: str = field(default_factory=lambda: os.getenv("DUMMYJSON_USERNAME", "emilys"))
    auth_password: str = field(default_factory=lambda: os.getenv("DUMMYJSON_PASSWORD", "emilyspass"))

    def __post_init__(self) -> None:
        self.config_signature = hashlib.sha256(
            f"dummyjson:{self.auth_username}:{self.auth_password}".encode("utf-8")
        ).hexdigest()[:12]
        self.jsonplaceholder_posts = [
            {
                "userId": ((idx - 1) // 10) + 1,
                "id": idx,
                "title": f"Post {idx}",
                "body": f"Body {idx}",
            }
            for idx in range(1, 101)
        ]
        self.jsonplaceholder_comments = [
            {
                "postId": ((idx - 1) // 5) + 1,
                "id": idx,
                "name": f"Comment {idx}",
                "email": f"user{idx}@example.com",
                "body": f"Comment body {idx}",
            }
            for idx in range(1, 501)
        ]
        self.jsonplaceholder_albums = [
            {"userId": ((idx - 1) // 10) + 1, "id": idx, "title": f"Album {idx}"}
            for idx in range(1, 101)
        ]
        self.jsonplaceholder_photos = [
            {
                "albumId": ((idx - 1) // 50) + 1,
                "id": idx,
                "title": f"Photo {idx}",
                "url": f"https://example.local/photos/{idx}.jpg",
                "thumbnailUrl": f"https://example.local/photos/{idx}-thumb.jpg",
            }
            for idx in range(1, 5001)
        ]
        self.jsonplaceholder_todos = [
            {
                "userId": ((idx - 1) // 20) + 1,
                "id": idx,
                "title": f"Todo {idx}",
                "completed": idx % 2 == 0,
            }
            for idx in range(1, 201)
        ]
        self.jsonplaceholder_todos[0]["completed"] = False
        self.jsonplaceholder_users = self.build_jsonplaceholder_users()
        self.dummy_products = self.build_dummy_products()
        self.dummy_product_categories = sorted({item["category"] for item in self.dummy_products})
        self.dummy_users = self.build_dummy_users()
        self.dummy_posts = self.build_dummy_posts()
        self.dummy_comments = self.build_dummy_comments()
        self.dummy_todos = self.build_dummy_todos()
        self.dummy_quotes = self.build_dummy_quotes()
        self.dummy_login_payload = {
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token,
            "id": 1,
            "username": self.auth_username,
            "email": f"{self.auth_username}@x.dummyjson.com",
            "firstName": "Emily",
            "lastName": "Johnson",
            "gender": "female",
            "image": f"https://dummyjson.com/icon/{self.auth_username}/128",
        }
        self.dummy_auth_me_payload = {
            "id": 1,
            "username": self.auth_username,
            "email": f"{self.auth_username}@x.dummyjson.com",
            "firstName": "Emily",
            "lastName": "Johnson",
            "gender": "female",
            "image": f"https://dummyjson.com/icon/{self.auth_username}/128",
        }

    @staticmethod
    def get_by_id(items: list[dict[str, Any]], item_id: int) -> dict[str, Any]:
        for item in items:
            if item["id"] == item_id:
                return item
        raise HTTPException(status_code=404, detail=f"resource {item_id} not found")

    @staticmethod
    def build_jsonplaceholder_users() -> list[dict[str, Any]]:
        users = []
        names = [
            ("Leanne Graham", "Bret", "Gwenborough"),
            ("Ervin Howell", "Antonette", "Wisokyburgh"),
        ]
        for idx in range(1, 11):
            if idx <= len(names):
                name, username, city = names[idx - 1]
            else:
                name = f"User {idx}"
                username = f"user{idx}"
                city = f"City {idx}"
            users.append(
                {
                    "id": idx,
                    "name": name,
                    "username": username,
                    "email": f"user{idx}@example.com",
                    "address": {"city": city},
                    "company": {"name": f"Company {idx}"},
                }
            )
        return users

    @staticmethod
    def build_dummy_products() -> list[dict[str, Any]]:
        products = [
            {
                "id": 1,
                "title": "Essence Mascara Lash Princess",
                "description": "The Essence Mascara Lash Princess is a popular mascara.",
                "category": "beauty",
                "price": 9.99,
                "rating": 2.56,
                "thumbnail": "https://dummy.local/products/1-thumb.webp",
            },
            {
                "id": 2,
                "title": "Smartphone X Phone",
                "description": "A phone product for search",
                "category": "electronics",
                "price": 199.99,
                "rating": 4.2,
                "thumbnail": "https://dummy.local/products/2-thumb.webp",
            },
        ]
        for idx in range(3, 31):
            products.append(
                {
                    "id": idx,
                    "title": f"Product {idx}",
                    "description": f"Description {idx}",
                    "category": "groceries" if idx % 2 else "beauty",
                    "price": float(idx),
                    "rating": 3.0 + (idx % 5) * 0.1,
                    "thumbnail": f"https://dummy.local/products/{idx}-thumb.webp",
                }
            )
        return products

    def build_dummy_users(self) -> list[dict[str, Any]]:
        users = [
            {
                "id": 1,
                "firstName": "Emily",
                "lastName": "Johnson",
                "age": 28,
                "email": f"{self.auth_username}@x.dummyjson.com",
                "username": self.auth_username,
                "hair": {"color": "Brown"},
                "company": {"name": "Dooley, Kozey and Cronin"},
            }
        ]
        for idx in range(2, 31):
            users.append(
                {
                    "id": idx,
                    "firstName": f"User{idx}",
                    "lastName": "Dummy",
                    "age": 20 + idx,
                    "email": f"user{idx}@x.dummyjson.com",
                    "username": f"user{idx}",
                    "hair": {"color": "Brown" if idx % 3 == 0 else "Black"},
                    "company": {"name": f"Company {idx}"},
                }
            )
        return users

    @staticmethod
    def build_dummy_posts() -> list[dict[str, Any]]:
        posts = [
            {
                "id": 1,
                "title": "Love and Life",
                "body": "A dummy post body",
                "userId": 1,
                "tags": ["life", "story"],
                "reactions": {"likes": 10, "dislikes": 1},
            },
            {
                "id": 2,
                "title": "Another Love Story",
                "body": "Post body 2",
                "userId": 5,
                "tags": ["love", "fiction"],
                "reactions": {"likes": 20, "dislikes": 2},
            },
        ]
        for idx in range(3, 31):
            posts.append(
                {
                    "id": idx,
                    "title": f"Post {idx}",
                    "body": f"Dummy post body {idx}",
                    "userId": 5 if idx == 5 else ((idx - 1) % 10) + 1,
                    "tags": ["tag", f"tag{idx}"],
                    "reactions": {"likes": idx, "dislikes": idx % 3},
                }
            )
        return posts

    @staticmethod
    def build_dummy_comments() -> list[dict[str, Any]]:
        comments = []
        for idx in range(1, 31):
            post_id = 1 if idx <= 3 else ((idx - 1) % 10) + 1
            comments.append(
                {
                    "id": idx,
                    "body": f"Comment body {idx}",
                    "postId": post_id,
                    "likes": idx % 7,
                    "user": {
                        "id": idx,
                        "username": f"user{idx}",
                        "fullName": f"User {idx}",
                    },
                }
            )
        return comments

    @staticmethod
    def build_dummy_todos() -> list[dict[str, Any]]:
        todos = [
            {"id": 1, "todo": "Do something nice", "completed": False, "userId": 26},
            {"id": 2, "todo": "Write unit tests", "completed": True, "userId": 2},
            {"id": 3, "todo": "Listen to music", "completed": False, "userId": 1},
            {"id": 4, "todo": "Read docs", "completed": True, "userId": 1},
        ]
        for idx in range(5, 31):
            todos.append(
                {
                    "id": idx,
                    "todo": f"Todo item {idx}",
                    "completed": idx % 2 == 0,
                    "userId": ((idx - 1) % 10) + 1,
                }
            )
        return todos

    @staticmethod
    def build_dummy_quotes() -> list[dict[str, Any]]:
        return [
            {"id": idx, "quote": f"Quote text {idx}", "author": f"Author {idx}"}
            for idx in range(1, 31)
        ]


app = create_app()
