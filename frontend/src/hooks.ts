import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type NewProduct } from "./api";

export const useStores = () =>
  useQuery({ queryKey: ["stores"], queryFn: api.stores, staleTime: Infinity });

export const useProducts = () => useQuery({ queryKey: ["products"], queryFn: api.products });

export const useProduct = (id: number) =>
  useQuery({ queryKey: ["products", id], queryFn: () => api.product(id) });

/** Any change to a product refreshes every product query. */
function useInvalidating<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => client.invalidateQueries({ queryKey: ["products"] }),
  });
}

export const useAddProduct = () => useInvalidating((body: NewProduct) => api.create(body));
export const useCheckAll = () => useInvalidating(() => api.checkAll());
export const useCheckOne = () => useInvalidating((id: number) => api.check(id));
export const useRemoveProduct = () => useInvalidating((id: number) => api.remove(id));
export const useSetTarget = () =>
  useInvalidating(({ id, target }: { id: number; target: number }) =>
    api.update(id, { target_price: target }),
  );
