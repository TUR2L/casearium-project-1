import sys
import unittest
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from b2c_consultant import FALLBACK_TEXT, process_b2c_consultation


class B2CConsultantTests(unittest.TestCase):
    def test_activation_only_for_b2c_consultation(self):
        payload = {
            "question_text": "Какие тарифы доступны?",
            "dialog_context": {"messages_history": []},
            "client_type": "B2B",
            "topic": "consultation",
        }
        result = process_b2c_consultation(payload)
        self.assertFalse(result["answer_found"])
        self.assertIn("не применим", result["answer_text"])

    def test_answer_found_for_public_tariff_question(self):
        payload = {
            "question_text": "Какие тарифы доступны для физических лиц?",
            "dialog_context": {"messages_history": []},
            "client_type": "B2C",
            "topic": "consultation",
        }
        result = process_b2c_consultation(payload)
        self.assertTrue(result["answer_found"])
        self.assertIn("тариф", result["answer_text"].lower())

    def test_context_resolves_short_follow_up_question(self):
        payload = {
            "question_text": "А сколько это стоит?",
            "dialog_context": {
                "messages_history": [
                    {"role": "client", "text": "Хочу подключить услугу для физлица"},
                    {"role": "agent", "text": "Могу подсказать по тарифам и стоимости"},
                ]
            },
            "client_type": "B2C",
            "topic": "consultation",
        }
        result = process_b2c_consultation(payload)
        self.assertTrue(result["answer_found"])
        self.assertIn("стоим", result["answer_text"].lower())

    def test_fallback_for_personal_data_request(self):
        payload = {
            "question_text": "Почему по моему договору списалась другая сумма?",
            "dialog_context": {"messages_history": []},
            "client_type": "B2C",
            "topic": "consultation",
        }
        result = process_b2c_consultation(payload)
        self.assertFalse(result["answer_found"])
        self.assertIn("индивидуальным данным", result["answer_text"])

    def test_fallback_for_empty_question(self):
        payload = {
            "question_text": "   ",
            "dialog_context": {"messages_history": []},
            "client_type": "B2C",
            "topic": "consultation",
        }
        result = process_b2c_consultation(payload)
        self.assertEqual(result, {"answer_text": FALLBACK_TEXT, "answer_found": False})

    def test_fallback_for_irrelevant_question_not_in_public_kb(self):
        payload = {
            "question_text": "Какая погода в Москве на завтра?",
            "dialog_context": {"messages_history": []},
            "client_type": "B2C",
            "topic": "consultation",
        }
        result = process_b2c_consultation(payload)
        self.assertEqual(result, {"answer_text": FALLBACK_TEXT, "answer_found": False})


if __name__ == "__main__":
    unittest.main()
