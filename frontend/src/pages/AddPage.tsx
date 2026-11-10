import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import type { Category } from "../api";
import { useAddCategory, useAddProduct, useCategories, useCheckOne, useStores } from "../hooks";

/** "Pin a new window": a taped paper note with the fields, and an empty window beside it. */
export function AddPage() {
  const navigate = useNavigate();
  const add = useAddProduct();
  const addCategory = useAddCategory();
  const check = useCheckOne();
  const { data: stores = [] } = useStores();
  const { data: categories = [] } = useCategories();

  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [floorId, setFloorId] = useState<number | null>(null);
  const [room, setRoom] = useState("");
  const [alert, setAlert] = useState("");
  const [newFloor, setNewFloor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const floors = categories.filter((c) => c.parent_id === null);
  const rooms = categories.filter((c) => floorId !== null && c.parent_id === floorId);

  async function createFloor() {
    const floorName = newFloor?.trim();
    if (!floorName) return;
    setError(null);
    try {
      const floor = await addCategory.mutateAsync({ name: floorName });
      setFloorId(floor.id);
      setNewFloor(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't add that floor.");
    }
  }

  async function roomId(): Promise<number | undefined> {
    if (floorId === null) return undefined;
    const roomName = room.trim();
    if (!roomName) return floorId;
    const existing = rooms.find((r) => r.name.toLowerCase() === roomName.toLowerCase());
    if (existing) return existing.id;
    const created: Category = await addCategory.mutateAsync({ name: roomName, parent_id: floorId });
    return created.id;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!url.trim() || !name.trim()) {
      setError("Add both the product link and a name you'll recognise.");
      return;
    }
    const alertNumber = alert ? Number(alert.replace(",", ".")) : undefined;
    if (alert && (!alertNumber || alertNumber <= 0)) {
      setError("Alert price must be a number, like 249,90.");
      return;
    }
    setSaving(true);
    try {
      const product = await add.mutateAsync({
        url: url.trim(),
        name: name.trim(),
        category_id: await roomId(),
        target_price: alertNumber,
      });
      // First check right away, so the window has a price and a photo. A failure shows on the next page.
      await check.mutateAsync(product.id).catch(() => undefined);
      navigate(`/products/${product.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save this product.");
      setSaving(false);
    }
  }

  return (
    <div className="pin">
      <h1 className="pin__title">pin a new window</h1>

      <div className="pin__stage">
        <form className="pin-note paper paper--taped" onSubmit={submit} noValidate>
          <label className="line-field">
            <span className="line-field__label">Product link</span>
            <input
              type="url"
              inputMode="url"
              placeholder="https://www.gratis.com/…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>

          <label className="line-field">
            <span className="line-field__label">Name</span>
            <input placeholder="AHA BHA PHA toner" value={name} onChange={(e) => setName(e.target.value)} />
          </label>

          <fieldset className="chips">
            <legend className="line-field__label">Floor</legend>
            {floors.map((floor) => (
              <label key={floor.id} className="chip">
                <input
                  type="radio"
                  name="floor"
                  checked={floorId === floor.id}
                  onChange={() => {
                    setFloorId(floor.id);
                    setRoom("");
                  }}
                />
                <span>{floor.name.toLowerCase()}</span>
              </label>
            ))}
            {newFloor === null ? (
              <button type="button" className="chip chip--new" onClick={() => setNewFloor("")}>
                + new floor
              </button>
            ) : (
              <span className="chip-new">
                <input
                  aria-label="New floor name"
                  placeholder="Pets"
                  value={newFloor}
                  onChange={(e) => setNewFloor(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void createFloor();
                    }
                  }}
                  autoFocus
                />
                <button type="button" className="text-button" onClick={() => void createFloor()}>
                  Add floor
                </button>
              </span>
            )}
          </fieldset>

          <label className="line-field">
            <span className="line-field__label">Room</span>
            <input
              list="rooms"
              placeholder={floorId === null ? "Pick a floor first" : "Toners"}
              disabled={floorId === null}
              value={room}
              onChange={(e) => setRoom(e.target.value)}
            />
            <datalist id="rooms">
              {rooms.map((r) => (
                <option key={r.id} value={r.name} />
              ))}
            </datalist>
          </label>

          <label className="line-field line-field--short">
            <span className="line-field__label">Alert me at</span>
            <input
              inputMode="decimal"
              placeholder="249,90"
              value={alert}
              onChange={(e) => setAlert(e.target.value)}
            />
          </label>

          <button className="paper-button paper-button--mustard" type="submit" disabled={saving}>
            {saving ? "Starting…" : "Start tracking"}
          </button>

          {error ? (
            <p className="pin-note__error" role="alert">
              {error}
            </p>
          ) : (
            <p className="pin-note__hint">
              Works with {stores.map((s) => s.name).join(", ") || "the supported stores"}.
            </p>
          )}
        </form>

        <div className="pin__preview" aria-hidden="true">
          <span className="empty-window" />
          <span className="pin__preview-label paper">{name.trim() || "your new window"}</span>
        </div>
      </div>
    </div>
  );
}
