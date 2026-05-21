import {
  type QueryKey,
  type UseMutationOptions,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"

import type { ApiError } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type AnyQueryKey = QueryKey | QueryKey[]

interface UseCrudMutationOptions<TData, TVariables>
  extends Omit<
    UseMutationOptions<TData, ApiError, TVariables>,
    "mutationFn" | "onError" | "onSettled"
  > {
  mutationFn: (variables: TVariables) => Promise<TData>
  /**
   * Query keys to invalidate after the mutation settles. Pass either a single
   * QueryKey (e.g. `["recipes"]`) or an array of them (e.g. `[["recipes"],
   * ["recipe", id]]`) when more than one cache slot needs to be refreshed.
   */
  invalidateKeys?: AnyQueryKey
  /** Optional toast message on success. Skipped when omitted. */
  successMessage?: string
}

const isQueryKeyArray = (value: AnyQueryKey): value is QueryKey[] =>
  Array.isArray(value) && value.length > 0 && Array.isArray(value[0])

export function useCrudMutation<TData, TVariables = void>({
  mutationFn,
  invalidateKeys,
  successMessage,
  onSuccess,
  ...rest
}: UseCrudMutationOptions<TData, TVariables>) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  return useMutation<TData, ApiError, TVariables>({
    ...rest,
    mutationFn,
    onSuccess: (...args) => {
      if (successMessage) showSuccessToast(successMessage)
      onSuccess?.(...args)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      if (!invalidateKeys) return
      const keys = isQueryKeyArray(invalidateKeys)
        ? invalidateKeys
        : [invalidateKeys]
      for (const key of keys) {
        queryClient.invalidateQueries({ queryKey: key })
      }
    },
  })
}
