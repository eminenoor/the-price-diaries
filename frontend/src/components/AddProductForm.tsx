import { useState, type FormEvent } from "react";

import { useAddProduct, useStores } from "../hooks";

export function AddProductForm() {
  const add = useAddProduct();
  const { data: stores = [] } = useStores();
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!url.trim() || !name.trim()) {
      setError("Add both the product link and a name you'll recognise.");
      return;
    }
    const targetNumber = target ? Number(target.replace(",", ".")) : undefined;
    if (target && (!targetNumber || targetNumber <= 0)) {
      setError("Target price must be a number, like 249,90.");
      return;
    }
    try {
      await add.mutateAsync({
        url: url.trim(),
        name: name.trim(),
        target_price: targetNumber,
      });
      setUrl("");
      setName("");
      setTarget("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save this product.");
    }
  }

  const storeNames = stores.map((s) => s.name).join(", ");

  return (
    <form className="add-form" onSubmit={submit} noValidate>
      <h2 className="add-form__title">Track a product</h2>
      <div className="add-form__fields">
        <label className="field field--url">
          <span className="field__label">Product link</span>
          <input
            type="url"
            inputMode="url"
            placeholder="https://www.gratis.com/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field__label">Name</span>
          <input
            placeholder="Vitamin C serum"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="field field--short">
          <span className="field__label">Alert me at</span>
          <input
            inputMode="decimal"
            placeholder="249,90"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        </label>
        <button className="button button--primary" type="submit" disabled={add.isPending}>
          {add.isPending ? "Saving…" : "Start tracking"}
        </button>
      </div>
      {error ? (
        <p className="add-form__error" role="alert">
          {error}
        </p>
      ) : (
        <p className="add-form__hint">Works with {storeNames || "supported stores"}.</p>
      )}
    </form>
  );
}
