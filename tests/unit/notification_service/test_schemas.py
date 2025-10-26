import pytest
from pydantic import ValidationError
from notification_service.schemas import NotificationEventEnvelope
import copy


class TestSchemas:

    def test_ut002_invalid_payload_raises_validation_error(self, event_data_factory):
        """
        Tests UT-002: Verifies that a message with a missing required field
        in the payload fails validation.
        """
        invalid_data = event_data_factory()

        invalid_data['payload'] = copy.deepcopy(invalid_data['payload'])

        del invalid_data['payload']['credit_card']

        with pytest.raises(ValidationError, match="credit_card"):
            NotificationEventEnvelope.model_validate(invalid_data)
