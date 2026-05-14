import { useMutation } from '@tanstack/react-query';

import { postOAuthInit } from '../api/connectors.api';
import type { ConnectorName } from '../types/connector.types';

interface StartOAuthArgs {
  name: ConnectorName;
  shop: string;
}

export function useStartOAuthMutation() {
  return useMutation({
    mutationFn: ({ name, shop }: StartOAuthArgs) => postOAuthInit(name, shop),
  });
}
