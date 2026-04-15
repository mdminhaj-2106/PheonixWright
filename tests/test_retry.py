import pytest
import asyncio
from unittest.mock import patch, MagicMock

from agent.retry import RetryStrategy
from agent.exceptions import APIError, RetryExhaustedError

@pytest.mark.asyncio
async def test_backoff_delay_increases():
    strategy = RetryStrategy(max_retries=2, base_delay=0.1, max_delay=1.0)
    
    async def mock_func():
        raise APIError(500, "Server Error")
        
    with patch("asyncio.sleep") as mock_sleep:
        with pytest.raises(RetryExhaustedError):
            await strategy.execute_with_retry(mock_func)
            
        assert mock_sleep.call_count == 2
        call1 = mock_sleep.call_args_list[0][0][0]
        call2 = mock_sleep.call_args_list[1][0][0]
        assert call1 >= 0.1
        assert call2 >= 0.2

@pytest.mark.asyncio
async def test_permanent_error_not_retried():
    strategy = RetryStrategy(max_retries=3)
    
    mock_func = MagicMock(side_effect=APIError(400, "Bad Request"))
    
    with pytest.raises(APIError) as exc:
        await strategy.execute_with_retry(mock_func)
        
    assert exc.value.code == 400
    assert mock_func.call_count == 1

@pytest.mark.asyncio
async def test_retry_exhausted_error_raised():
    strategy = RetryStrategy(max_retries=1, base_delay=0.01)
    
    async def mock_func():
        raise APIError(429, "Too Many Requests")
        
    with pytest.raises(RetryExhaustedError) as exc:
        await strategy.execute_with_retry(mock_func)
        
    assert "retries consumed" in str(exc.value)
