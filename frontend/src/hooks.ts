import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type NewCategory, type NewProduct } from "./api";

export const useStores = () =>
  useQuery({ queryKey: ["stores"], queryFn: api.stores, staleTime: Infinity });

export const useCategories = () => useQuery({ queryKey: ["categories"], queryFn: api.categories });

export const useAddCategory = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewCategory) => api.createCategory(body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["categories"] }),
  });
};

export const useProducts = () => useQuery({ queryKey: ["products"], queryFn: api.products });

export const useProduct = (id: number) =>
  useQuery({ queryKey: ["products", id], queryFn: () => api.product(id) });

/**
 * Any change to a product refreshes every product query, and the notes: a check can add
 * notes, and a product's notes go when it's no longer tracked.
 */
function useInvalidating<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["products"] }),
        client.invalidateQueries({ queryKey: ["notifications"] }),
      ]),
  });
}

export const useAddProduct = () => useInvalidating((body: NewProduct) => api.create(body));
export const useCheckAll = () => useInvalidating(() => api.checkAll());
export const useCheckOne = () => useInvalidating((id: number) => api.check(id));
export const useRemoveProduct = () => useInvalidating((id: number) => api.remove(id));
/** brand "" removes the brand. */
export const useSetBrand = () =>
  useInvalidating(({ id, brand }: { id: number; brand: string }) => api.update(id, { brand }));
export const useSetTarget = () =>
  useInvalidating(({ id, target }: { id: number; target: number }) =>
    api.update(id, { target_price: target }),
  );
/** One name for the product at every store; "" goes back to the stores' names. */
export const useSetDisplayName = () =>
  useInvalidating(({ id, name }: { id: number; name: string }) =>
    api.update(id, { display_name: name }),
  );
/** Group a product with the same product at another store. */
export const useLink = () =>
  useInvalidating(({ id, otherId }: { id: number; otherId: number }) => api.link(id, otherId));
/** Take a product out of its group, for good: checks won't regroup it by barcode. */
export const useUnlink = () => useInvalidating((id: number) => api.unlink(id));
/** The inbox. Refreshed every few minutes, so the morning check's notes show up on their own. */
export const useNotes = () =>
  useQuery({ queryKey: ["notifications"], queryFn: api.notes, refetchInterval: 5 * 60_000 });

function useNotesChange<TArgs>(fn: (args: TArgs) => Promise<void>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

/** The Sunday paper for the week a date falls in (null: the latest). */
export const usePaper = (week: string | null) =>
  useQuery({ queryKey: ["paper", week ?? "latest"], queryFn: () => api.paper(week) });

export const useReadNote = () => useNotesChange((id: number) => api.readNote(id));
export const useReadAllNotes = () => useNotesChange(() => api.readAllNotes());

/** size "" removes the size; anything else is parsed by the backend ("1,5 L"). */
export const useSetSize = () =>
  useInvalidating(({ id, size }: { id: number; size: string }) => api.update(id, { size }));
