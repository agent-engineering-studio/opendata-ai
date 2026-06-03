import Link from "next/link";

// Bootstrap Italia "it-footer" markup. Design React Kit does not ship a
// Footer component, but the CSS classes from bootstrap-italia provide the
// institutional look out of the box.
export function SiteFooter() {
  return (
    <footer className="it-footer" role="contentinfo">
      <div className="it-footer-main">
        <div className="container">
          <section>
            <div className="row clearfix">
              <div className="col-sm-12">
                <div className="it-brand-wrapper">
                  <Link className="it-brand-text" href="/">
                    <h2 className="no_toc">OpenData AI</h2>
                    <h3 className="no_toc d-none d-md-block">
                      Open data CKAN + statistiche ufficiali
                    </h3>
                  </Link>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <div className="it-footer-small-prints clearfix">
        <div className="container">
          <ul className="it-footer-small-prints-list list-inline mb-0 d-flex flex-column flex-md-row">
            <li className="list-inline-item">
              <Link href="/accessibilita">Dichiarazione di accessibilità</Link>
            </li>
            <li className="list-inline-item">
              <Link href="/note-legali">Note legali</Link>
            </li>
            <li className="list-inline-item">
              <Link href="/privacy">Privacy policy</Link>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
