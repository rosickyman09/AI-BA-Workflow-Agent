DELETE FROM user_api_keys WHERE label='stage7h-acceptance';
INSERT INTO user_api_keys (id, "userId", label, "apiKey", scopes, audience)
VALUES ('11111111-2222-3333-4444-555555555555', 'd3f49c65-f09e-427f-906b-14357338df89', 'stage7h-acceptance', 'stage7h-test-key-20260319', '["workflow:create","workflow:read","workflow:update","workflow:execute"]', 'public-api');
