import { Link, Route, Routes } from "react-router-dom";

import { useCheckAll, useProducts } from "./hooks";
import { IndexPage } from "./pages/IndexPage";
import { ProductPage } from "./pages/ProductPage";

export function App() {
  return (
    <div className="page">
      <Masthead />
      <main>
        <Routes>
          <Route path="/" element={<IndexPage />} />
          <Route path="/products/:id" element={<ProductPage />} />
          <Route
            path="*"
            element={
              <p className="status">
                Nothing here. <Link to="/">Back to your products</Link>
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

function Masthead() {
  const checkAll = useCheckAll();
  const { data: products = [] } = useProducts();
  const failed = checkAll.data?.filter((r) => !r.ok).length ?? 0;

  return (
    <header className="masthead">
      <Link to="/" className="wordmark" aria-label="The Price Diaries, home">
        The Price Diaries
      </Link>
      <p className="masthead__tagline">For the things you buy again</p>
      <div className="masthead__actions">
        <button
          type="button"
          className="button"
          onClick={() => checkAll.mutate()}
          disabled={checkAll.isPending || products.length === 0}
        >
          {checkAll.isPending ? "Checking all prices…" : "Check all prices now"}
        </button>
        {checkAll.isSuccess && (
          <span className="masthead__result" role="status">
            {failed === 0 ? "All prices updated" : `${failed} couldn't be checked`}
          </span>
        )}
      </div>
    </header>
  );
}
