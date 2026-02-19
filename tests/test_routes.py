"""Tests for the Todo API endpoints."""


class TestCreateTodo:
    """Tests for POST /todos."""

    async def test_create_todo_with_valid_data(self, client):
        response = await client.post(
            "/todos", json={"title": "Buy groceries", "description": "Milk, eggs, bread"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Buy groceries"
        assert data["description"] == "Milk, eggs, bread"
        assert data["completed"] is False
        assert "id" in data
        assert "created_at" in data

    async def test_create_todo_without_description(self, client):
        response = await client.post("/todos", json={"title": "Simple todo"})
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Simple todo"
        assert data["description"] is None

    async def test_create_todo_with_empty_title_returns_422(self, client):
        response = await client.post("/todos", json={"title": ""})
        assert response.status_code == 422

    async def test_create_todo_without_title_returns_422(self, client):
        response = await client.post("/todos", json={})
        assert response.status_code == 422

    async def test_create_todo_with_long_title_returns_422(self, client):
        response = await client.post("/todos", json={"title": "x" * 201})
        assert response.status_code == 422


class TestListTodos:
    """Tests for GET /todos."""

    async def test_list_todos_empty(self, client):
        response = await client.get("/todos")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_todos_returns_all(self, client):
        await client.post("/todos", json={"title": "Todo 1"})
        await client.post("/todos", json={"title": "Todo 2"})
        response = await client.get("/todos")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_list_todos_filter_completed(self, client):
        resp1 = await client.post("/todos", json={"title": "Todo 1"})
        todo_id = resp1.json()["id"]
        await client.patch(f"/todos/{todo_id}", json={"completed": True})
        await client.post("/todos", json={"title": "Todo 2"})

        # Filter completed
        response = await client.get("/todos?completed=true")
        data = response.json()
        assert len(data) == 1
        assert data[0]["completed"] is True

        # Filter not completed
        response = await client.get("/todos?completed=false")
        data = response.json()
        assert len(data) == 1
        assert data[0]["completed"] is False


class TestGetTodo:
    """Tests for GET /todos/{id}."""

    async def test_get_existing_todo(self, client, sample_todo):
        response = await client.get(f"/todos/{sample_todo['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_todo["id"]
        assert data["title"] == sample_todo["title"]

    async def test_get_nonexistent_todo_returns_404(self, client):
        response = await client.get("/todos/99999")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"
        assert data["resource"] == "todo"


class TestUpdateTodo:
    """Tests for PATCH /todos/{id}."""

    async def test_update_title(self, client, sample_todo):
        response = await client.patch(
            f"/todos/{sample_todo['id']}", json={"title": "Updated Title"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == sample_todo["description"]

    async def test_mark_completed(self, client, sample_todo):
        response = await client.patch(f"/todos/{sample_todo['id']}", json={"completed": True})
        assert response.status_code == 200
        assert response.json()["completed"] is True

    async def test_update_nonexistent_todo_returns_404(self, client):
        response = await client.patch("/todos/99999", json={"title": "New"})
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"
        assert data["resource"] == "todo"


class TestDeleteTodo:
    """Tests for DELETE /todos/{id}."""

    async def test_delete_existing_todo(self, client, sample_todo):
        response = await client.delete(f"/todos/{sample_todo['id']}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"/todos/{sample_todo['id']}")
        assert get_response.status_code == 404
        assert get_response.json()["error_code"] == "NOT_FOUND"

    async def test_delete_nonexistent_todo_returns_404(self, client):
        response = await client.delete("/todos/99999")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "NOT_FOUND"
        assert data["resource"] == "todo"
