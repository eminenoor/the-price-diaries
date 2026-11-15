import { Link, Route, Routes, useLocation } from "react-router-dom";

import { SvgFilters } from "./components/SvgFilters";
import { useCheckAll, useNotes, useProducts } from "./hooks";
import { useMode } from "./mode";
import { AddPage } from "./pages/AddPage";
import { IndexPage } from "./pages/IndexPage";
import { NotesPage } from "./pages/NotesPage";
import { ProductPage } from "./pages/ProductPage";
import { unreadLabel } from "./scene";

export function App() {
  return (
    <div className="page">
      <SvgFilters />
      <TopBar />
      <main id="main">
        <Routes>
          <Route path="/" element={<IndexPage />} />
          <Route path="/add" element={<AddPage />} />
          <Route path="/products/:id" element={<ProductPage />} />
          <Route path="/notes" element={<NotesPage />} />
          <Route
            path="*"
            element={
              <p className="status">
                Nothing here. <Link to="/">Back to the building</Link>
              </p>
            }
          />
        </Routes>
      </main>
      <footer className="colophon">
        Prices are checked once every morning, gently, one page at a time. Personal use only.
      </footer>
    </div>
  );
}

export function TopBar() {
  const checkAll = useCheckAll();
  const { data: products = [] } = useProducts();
  const { data: notes } = useNotes();
  const { mode, setMode } = useMode();
  const path = useLocation().pathname;
  const failed = checkAll.data?.filter((r) => !r.ok).length ?? 0;
  const unread = unreadLabel(notes?.unread ?? 0);

  return (
    <header className="topbar">
      <Link to="/" className="topbar__home" aria-current={path === "/" ? "page" : undefined}>
        The Price Diaries
      </Link>
      <div className="topbar__actions">
        <Link className="notes-link" to="/notes" aria-current={path === "/notes" ? "page" : undefined}>
          Notes
          {unread && (
            <>
              <span className="visually-hidden">,</span> <span className="notes-link__count">{unread}</span>
            </>
          )}
        </Link>
        <Link className="paper-button paper-button--mustard" to="/add">
          Pin a new window
        </Link>
        <button
          type="button"
          className="paper-button"
          onClick={() => checkAll.mutate()}
          disabled={checkAll.isPending || products.length === 0}
        >
          {checkAll.isPending ? "Checking all prices…" : "Check all prices now"}
        </button>
        {checkAll.isSuccess && (
          <span className="topbar__result" role="status">
            {failed === 0 ? "All prices updated" : `${failed} couldn't be checked`}
          </span>
        )}
        <button
          type="button"
          className="mode-toggle"
          onClick={() => setMode(mode === "night" ? "quiet" : "night")}
        >
          {mode === "night" ? "Switch to quiet mode" : "Switch to night view"}
        </button>
      </div>
    </header>
  );
}
