import pytest
from unittest.mock import patch, MagicMock
from logger.decorators import log_action, log_view, log_class_view
from django.test import RequestFactory
from django.http import JsonResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View



class TestLogActionDecorator:

    @patch("logger.utils.get_current_request", return_value=MagicMock())
    @patch("logger.utils.get_user_context", return_value=(None, '127.0.0.1', None, None))
    @patch("logger.decorators.log")
    def test_log_action_success(
            self, mock_log, mock_user_context, mock_get_request
    ):
        @log_action(action_type="TEST", level='INFO')
        def dummy_func(x, y):
            return x+y
        
        result = dummy_func(2, 3)

        assert result == 5

        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        assert kwargs["level"] == "INFO"
        assert kwargs["action_type"] == "TEST"
        assert "Function dummy_func executed" in kwargs["message"]
        assert kwargs["extra_data"]["function"] == "dummy_func"
        assert kwargs["extra_data"]["exception"] is None


    @patch("logger.utils.get_current_request", return_value=MagicMock())
    @patch("logger.utils.get_user_context", return_value=(None, '127.0.0.1', None, None))
    @patch("logger.decorators.log")    
    def test_log_action_exception(
            self, mock_log, mock_user_context, mock_get_request
    ):
        @log_action(action_type="TEST", level="INFO")
        def faulty_func():
           raise ValueError("Boom!")
        
        with pytest.raises(ValueError):
            faulty_func()

        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args        
        assert kwargs["level"] == "ERROR"
        assert "Exception in faulty_func:Boom!" in kwargs["message"]
        assert "Boom!" in kwargs["extra_data"]["exception"]
        

    @patch("logger.decorators.get_current_request", return_value=MagicMock())
    @patch("logger.decorators.get_user_context", return_value=(None, '127.0.0.1', None, None))
    @patch("logger.decorators.log", side_effect=Exception("log failed"))
    @patch("builtins.print")    
    def test_log_action_when_logging_fails(
         self, mock_print, mock_log, mock_user_context, mock_get_request   
    ):
        
        @log_action()    
        def simple_func():
            return "OK"
        
        result = simple_func()
        assert result == "OK"

        mock_print.assert_any_call("[WARN] Logging failed simple_func:log failed")

    

class TestViewLogDecorators:

    @patch("logger.decorators.get_user_context", return_value=("testuser", "10.0.0.10", "Chrome", None))
    @patch("logger.decorators.log")
    def test_log_view_success(self, mock_log, mock_user_context):

        factory = RequestFactory()
        request = factory.get("/test_path", HTTP_USER_AGENT="Chrome")
        
        @log_view(action_type="VIEW_TEST", level="INFO")
        def test_view(request):
            return JsonResponse({"ok": True}, status=200)
        
        response = test_view(request)

        assert response.status_code == 200
        mock_log.assert_called_once()

        _, kwargs = mock_log.call_args
        assert kwargs["level"] == "INFO"
        assert kwargs["user"] == "testuser"
        assert kwargs["ip_address"] == "10.0.0.10"
        assert kwargs["user_agent"] == "Chrome"
        assert kwargs["request_path"] == "/test_path"
        assert kwargs["extra_data"]["view_name"] == "test_view"
        assert kwargs["extra_data"]["status_code"] == 200
        assert "View test_view accessed" in kwargs["message"]

    @patch("logger.decorators.get_user_context", return_value=("usertesti", "11.12.13.14", "FireFox", None))
    @patch("logger.decorators.log")
    def test_log_view_exception(self, mock_log, mock_user_context):

        factory = RequestFactory()
        request = factory.get('/fail')

        @log_view(action_type="VIEW_FAIL", level="INFO")
        def failing_view(request):
            raise ValueError("Something went wrong")
        
        with pytest.raises(ValueError):
            failing_view(request)

        mock_log.assert_called_once()

        _, kwargs = mock_log.call_args
        assert kwargs["level"] == "ERROR"
        assert "Something went wrong" in kwargs["extra_data"]["exception"]
        assert "Exception in view failing_view:Something went wrong" in kwargs["message"]

    
class TestLogClassView:

    @patch("logger.decorators.get_user_context", return_value=("user", "1.2.3.4", "curl", None))
    @patch("logger.decorators.log")
    def test_log_class_view_success(self, mock_log, mock_user_context):
        
        factory = RequestFactory()
        request= factory.get("/some-path")

        class MyView(View):
            @log_class_view(action_type="REQUEST", level="INFO")
            def get(self, request):
               response = MagicMock()
               response.status_code = 200
               return response

        view_instance = MyView()
        result = view_instance.get(request)

        assert result.status_code == 200
        mock_log.assert_called_once()

        _, kwargs = mock_log.call_args

        assert kwargs["level"] == "INFO"
        assert kwargs["action_type"] == "READ"
        assert kwargs["message"] == "MyView.get executed"
        assert kwargs["request_path"] == "/some-path"
        assert kwargs["extra_data"]["status_code"] == 200
        assert kwargs["extra_data"]["http_method"] == "GET"
        assert kwargs["extra_data"]["exception"] is None

    
    @patch("logger.decorators.get_user_context", return_value=("user", "1.2.3.4", "curl", None))
    @patch("logger.decorators.log")    
    def test_log_class_exception(self, mock_log, mock_user_context):

        factory = RequestFactory()
        request = factory.get("/test-view/")

        class MyFailingView(View):
            @log_class_view(action_type="REQUEST", level="INFO")
            def get(self, request):
                raise ValueError("Something is wrong")
            
        view_instance = MyFailingView()

        with pytest.raises(ValueError):
            view_instance.get(request)

        mock_log.assert_called_once()
        _, kwargs = mock_log.call_args

        assert kwargs["level"] == "ERROR"
        assert kwargs["message"] == "Exception in MyFailingView.get: Something is wrong"
        assert "Something is wrong" in kwargs["extra_data"]["exception"] 


    @patch("logger.decorators.get_user_context", return_value=("user", "1.2.3.4", "curl", None))
    @patch("logger.decorators.log")
    def test_log_class_with_specific_method(self, mock_log, mock_user_context):

        factory = RequestFactory()
        request = factory.get("/get-path")

        class TestView(View):
            @log_class_view(action_type="REQUEST", level="INFO", methods=["post"])
            def get(self, request):
                reponse = MagicMock
                reponse.status_code = 200
                return reponse
            
        view_instance = TestView()
        result = view_instance.get(request)

        assert result.status_code == 200
        mock_log.assert_not_called()
        
