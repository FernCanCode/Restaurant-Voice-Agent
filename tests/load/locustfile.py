from locust import HttpUser, between, task


class RestaurantVoiceUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        response = self.client.post("/api/sessions", json={"channel": "browser"})
        response.raise_for_status()
        self.session_id = response.json()["session_id"]

    def _post_turn(self, utterance: str, name: str) -> None:
        with self.client.post(
            "/api/turn",
            name=name,
            json={
                "session_id": self.session_id,
                "utterance": utterance,
                "channel": "browser",
                "metadata": {},
            },
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Unexpected status {response.status_code}")
                return
            body = response.json()
            if "agent_text" not in body:
                response.failure("Missing agent_text in response")

    @task(2)
    def ask_menu_question(self) -> None:
        self._post_turn("What tacos do you have?", "menu_question")

    @task(2)
    def add_item(self) -> None:
        self._post_turn(
            "Add one chicken taco with no onions.",
            "add_item",
        )

    @task(1)
    def ask_total(self) -> None:
        self._post_turn("What is my total?", "order_total")
