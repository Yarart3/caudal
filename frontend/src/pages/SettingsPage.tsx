import { useEffect, useState, type FormEvent } from 'react';
import { api, errorMessage, type Category, type CategoryKind, type Rule } from '../api';
import { AppShell } from '../AppShell';
import { CategorySelect } from '../components/CategorySelect';
import { notifyDataChanged, onDataChanged } from '../events';

const KINDS: { value: CategoryKind; label: string }[] = [
  { value: 'expense', label: 'Gastos' },
  { value: 'income', label: 'Ingresos' },
];
const NEW_COLOR = '#5B616B';

/** Ajustes → Categorías y reglas (Fase 1c). Usuarios y formatos llegan en la Fase 4. */
export function SettingsPage() {
  const [categories, setCategories] = useState<Category[] | null>(null);
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.categories(), api.rules()])
      .then(([cats, rls]) => {
        if (!alive) return;
        setCategories(cats);
        setRules(rls);
      })
      .catch((err: unknown) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [reload]);

  useEffect(() => onDataChanged(() => setReload((n) => n + 1)), []);

  /** Ejecuta un cambio, avisa al resto de la app y enseña el mensaje (o el error). */
  async function run(action: () => Promise<string | null>): Promise<boolean> {
    setError(null);
    setMessage(null);
    try {
      const text = await action();
      setMessage(text);
      notifyDataChanged();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  }

  return (
    <AppShell title="Ajustes" current="Ajustes">
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="ok" role="status">
          {message}
        </p>
      )}
      {categories === null || rules === null ? (
        !error && <p className="muted">Cargando…</p>
      ) : (
        <section className="r2e">
          <CategoriesCard categories={categories} run={run} />
          <RulesCard rules={rules} categories={categories} run={run} />
        </section>
      )}
    </AppShell>
  );
}

type Run = (action: () => Promise<string | null>) => Promise<boolean>;

// ---------- Categorías ----------

function CategoriesCard({ categories, run }: { categories: Category[]; run: Run }) {
  const [name, setName] = useState('');
  const [kind, setKind] = useState<CategoryKind>('expense');
  const [color, setColor] = useState(NEW_COLOR);
  const [busy, setBusy] = useState(false);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (name.trim() === '') return;
    setBusy(true);
    const ok = await run(async () => {
      const created = await api.createCategory({ name: name.trim(), kind, color });
      return `Categoría «${created.name}» creada`;
    });
    setBusy(false);
    if (ok) {
      setName('');
      setColor(NEW_COLOR);
    }
  }

  return (
    <div className="card panel">
      <h2>Categorías</h2>
      {KINDS.map(({ value, label }) => (
        <div key={value} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h3 className="sub">{label}</h3>
          <ul className="edit-list">
            {categories
              .filter((c) => c.kind === value)
              .map((c) => (
                // key con nombre y color: si cambian desde fuera, la fila se reinicia
                <CategoryRow key={`${c.id}-${c.name}-${c.color}`} category={c} run={run} />
              ))}
          </ul>
        </div>
      ))}

      <form className="add-form" onSubmit={handleCreate} noValidate>
        <h3 className="sub">Nueva categoría</h3>
        <div className="row" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <input
            type="color"
            className="swatch"
            aria-label="Color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
          />
          <div className="field" style={{ flex: '1 1 160px' }}>
            <label htmlFor="cat-nombre">Nombre</label>
            <input
              id="cat-nombre"
              type="text"
              maxLength={60}
              placeholder="Ej. Mascotas"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="cat-tipo">Tipo</label>
            <select
              id="cat-tipo"
              value={kind}
              onChange={(e) => setKind(e.target.value as CategoryKind)}
            >
              <option value="expense">Gasto</option>
              <option value="income">Ingreso</option>
            </select>
          </div>
          <button type="submit" className="btn" disabled={busy || name.trim() === ''}>
            {busy ? 'Creando…' : 'Crear'}
          </button>
        </div>
      </form>
    </div>
  );
}

function CategoryRow({ category, run }: { category: Category; run: Run }) {
  const [name, setName] = useState(category.name);
  const [color, setColor] = useState(category.color);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const dirty =
    name.trim() !== category.name || color.toLowerCase() !== category.color.toLowerCase();

  async function save() {
    if (name.trim() === '') return;
    setBusy(true);
    await run(async () => {
      await api.updateCategory(category.id, { name: name.trim(), color });
      return `Categoría «${name.trim()}» guardada`;
    });
    setBusy(false);
  }

  async function remove() {
    setBusy(true);
    const ok = await run(async () => {
      await api.deleteCategory(category.id);
      return `Categoría «${category.name}» borrada`;
    });
    if (!ok) setBusy(false);
  }

  const usage = [
    `${category.transactions} ${category.transactions === 1 ? 'movimiento' : 'movimientos'}`,
    `${category.rules} ${category.rules === 1 ? 'regla' : 'reglas'}`,
  ].join(' · ');

  return (
    <li className="edit-row">
      <div className="row" style={{ flexWrap: 'wrap' }}>
        <input
          type="color"
          className="swatch"
          aria-label={`Color de ${category.name}`}
          value={color}
          onChange={(e) => setColor(e.target.value)}
        />
        <input
          className="input"
          style={{ flex: '1 1 140px' }}
          type="text"
          maxLength={60}
          aria-label={`Nombre de ${category.name}`}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
          {usage}
        </span>
        {dirty && (
          <button type="button" className="btn btn-sm btn-accent" onClick={save} disabled={busy}>
            Guardar
          </button>
        )}
        {!confirming && (
          <button
            type="button"
            className="link-btn danger"
            onClick={() => setConfirming(true)}
            disabled={busy}
          >
            Borrar
          </button>
        )}
      </div>
      {confirming && (
        <div className="ask">
          <span>
            ¿Borrar «{category.name}»?
            {category.transactions > 0 &&
              ` Sus ${category.transactions} movimientos volverán a «por revisar» (o a la categoría de otra regla que encaje).`}
            {category.rules > 0 && ` También se borrarán sus ${category.rules} reglas.`}
          </span>
          <div className="row">
            <button
              type="button"
              className="btn btn-sm btn-danger"
              onClick={remove}
              disabled={busy}
            >
              {busy ? 'Borrando…' : 'Sí, borrar'}
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setConfirming(false)}
              disabled={busy}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

// ---------- Reglas ----------

function RulesCard({
  rules,
  categories,
  run,
}: {
  rules: Rule[];
  categories: Category[];
  run: Run;
}) {
  const [pattern, setPattern] = useState('');
  const [categoryId, setCategoryId] = useState<number | null>(categories[0]?.id ?? null);
  const [busy, setBusy] = useState(false);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (pattern.trim() === '') return;
    setBusy(true);
    const ok = await run(async () => {
      const saved = await api.saveRule({ pattern, category_id: categoryId, apply: true });
      const verb = saved.replaced ? 'sustituida' : 'creada';
      return `Regla «${saved.rule.pattern}» ${verb} · ${saved.categorized} por revisar categorizados`;
    });
    setBusy(false);
    if (ok) setPattern('');
  }

  async function reapply() {
    setBusy(true);
    await run(async () => {
      const result = await api.applyRules(true);
      return `Reglas aplicadas · ${result.categorized} categorizados automáticamente · ${result.review} por revisar`;
    });
    setBusy(false);
  }

  return (
    <div className="card panel">
      <div className="between">
        <h2>Reglas</h2>
        <button type="button" className="btn btn-sm" onClick={reapply} disabled={busy}>
          Reaplicar a todo
        </button>
      </div>
      <p className="muted" style={{ fontSize: 13 }}>
        Si el concepto contiene estas palabras (enteras, sin importar mayúsculas ni acentos), el
        movimiento va a esa categoría. Se miran en este orden y gana la primera que encaja.
        «Reaplicar a todo» vuelve a pasarlas por lo automático y lo pendiente; lo que pusiste a mano
        no se toca.
      </p>
      <ul className="edit-list">
        {rules.map((rule) => (
          <RuleRow
            key={`${rule.id}-${rule.pattern}-${rule.category_id}`}
            rule={rule}
            categories={categories}
            run={run}
          />
        ))}
      </ul>

      <form className="add-form" onSubmit={handleCreate} noValidate>
        <h3 className="sub">Nueva regla</h3>
        <div className="row" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="field" style={{ flex: '1 1 160px' }}>
            <label htmlFor="regla-texto">Si el concepto contiene</label>
            <input
              id="regla-texto"
              type="text"
              maxLength={120}
              placeholder="Ej. BON PREU"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
            />
          </div>
          <div className="field" style={{ flex: '1 1 160px' }}>
            <label htmlFor="regla-categoria">Categoría</label>
            <CategorySelect
              id="regla-categoria"
              categories={categories}
              value={categoryId}
              onChange={setCategoryId}
              emptyLabel="Dejar por revisar"
            />
          </div>
          <button type="submit" className="btn" disabled={busy || pattern.trim() === ''}>
            {busy ? 'Guardando…' : 'Crear'}
          </button>
        </div>
      </form>
    </div>
  );
}

function RuleRow({ rule, categories, run }: { rule: Rule; categories: Category[]; run: Run }) {
  const [pattern, setPattern] = useState(rule.pattern);
  const [categoryId, setCategoryId] = useState(rule.category_id);
  const [busy, setBusy] = useState(false);
  const dirty = pattern.trim().toUpperCase() !== rule.pattern || categoryId !== rule.category_id;

  async function save() {
    if (pattern.trim() === '') return;
    setBusy(true);
    await run(async () => {
      const saved = await api.updateRule(rule.id, { pattern, category_id: categoryId });
      return `Regla «${saved.pattern}» guardada. Usa «Reaplicar a todo» para corregir lo ya categorizado.`;
    });
    setBusy(false);
  }

  async function remove() {
    setBusy(true);
    const ok = await run(async () => {
      await api.deleteRule(rule.id);
      return `Regla «${rule.pattern}» borrada`;
    });
    if (!ok) setBusy(false);
  }

  return (
    <li className="edit-row rule-row">
      <input
        className="input"
        type="text"
        maxLength={120}
        aria-label={`Texto de la regla ${rule.pattern}`}
        value={pattern}
        onChange={(e) => setPattern(e.target.value)}
      />
      <span aria-hidden="true" className="muted">
        →
      </span>
      <div className="field">
        <CategorySelect
          ariaLabel={`Categoría de la regla ${rule.pattern}`}
          categories={categories}
          value={categoryId}
          onChange={setCategoryId}
          emptyLabel="Dejar por revisar"
        />
      </div>
      <div className="row" style={{ gap: 8 }}>
        <span
          className="badge"
          style={
            rule.created_by === 'user'
              ? { background: '#EEE6F0', color: '#62305F' }
              : { background: '#EEF0EC', color: '#4A5059' }
          }
        >
          {rule.created_by === 'user' ? 'Tuya' : 'Inicial'}
        </span>
        {dirty && (
          <button type="button" className="btn btn-sm btn-accent" onClick={save} disabled={busy}>
            Guardar
          </button>
        )}
        <button type="button" className="link-btn danger" onClick={remove} disabled={busy}>
          Borrar
        </button>
      </div>
    </li>
  );
}
