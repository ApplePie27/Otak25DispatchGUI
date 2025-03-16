import unittest
from dispatch_call_manager import DispatchCallManager
from datetime import datetime

class TestDispatchCallManager(unittest.TestCase):
    def setUp(self):
        self.manager = DispatchCallManager()
        self.manager.set_user("test_user")

    def test_add_call(self):
        call = {
            "InputMedium": "Radio",
            "Source": "Safety",
            "Caller": "John Doe",
            "Location": "A",
            "Code": "Green",
            "Description": "Test call",
            "ResolutionStatus": False
        }
        self.manager.add_call(call)
        self.assertEqual(len(self.manager.calls), 1)
        self.assertEqual(self.manager.calls[0]["CallID"], "DC250001")

    def test_resolve_call(self):
        call = {
            "InputMedium": "Radio",
            "Source": "Safety",
            "Caller": "John Doe",
            "Location": "A",
            "Code": "Green",
            "Description": "Test call",
            "ResolutionStatus": False
        }
        self.manager.add_call(call)
        self.manager.resolve_call("DC250001", "resolved_by_user")
        self.assertTrue(self.manager.calls[0]["ResolutionStatus"])
        self.assertEqual(self.manager.calls[0]["ResolvedBy"], "resolved_by_user")

    # Add more tests for modify_call, undo, redo, save_to_file, load_from_file, etc.

if __name__ == "__main__":
    unittest.main()