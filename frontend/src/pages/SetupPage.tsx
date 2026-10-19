import { useEffect, useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { api, errorMessage } from '../api';
import { Loading, Screen } from './Screen';

const MIN_LENGTH = 8;

type Passwords = { gerard: string; gerardRepeat: string; padres: string; padresRepeat: string };

const EMPTY: Passwords = { gerard: '', gerardRepeat: '', padres: '', padresRepeat: '' };

/** Comprueba el formulario antes de enviarlo. Devuelve el primer error o null. */
function validateSetup(p: Passwords): string | null {
  for (const [name, pwd, repeat] of [
    ['Gerard', p.gerard, p.gerardRepeat],
    ['Padres', p.padres, p.padresRepeat],
  ] as const) {
    if (pwd.length < MIN_LENGTH) {
      return `La contraseña de ${name} debe tener al menos ${MIN_LENGTH} caracteres`;
    }
    if (pwd !== repeat) return `Las dos contraseñas de ${name} no coinciden`;
  }
  if (p.gerard === p.padres) return 'Gerard y Padres deben tener contraseñas distintas';
  return null;
}

/** Asistente de primer arranque: crea gerard (admin) y padres con sus contraseñas. */
export function SetupPage() {
  const navigate = useNavigate();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [values, setValues] = useState<Passwords>(EMPTY);
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api
      .setupStatus()
      .then((status) => setNeedsSetup(status.needs_setup))
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  if (needsSetup === null && error === null) return <Loading />;
  // Si ya hay usuarios, el asistente no se puede repetir
  if (needsSetup === false) return <Navigate to="/" replace />;

  function update(field: keyof Passwords, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validateSetup(values);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setSending(true);
    try {
      await api.setup(values.gerard, values.padres);
      navigate('/entrar', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setSending(false);
    }
  }

  const type = show ? 'text' : 'password';

  return (
    <Screen foot="Las contraseñas no se guardan tal cual, solo su hash (Argon2). Apúntalas en un sitio seguro.">
      <h1 style={{ fontSize: 26 }}>Bienvenido a Caudal</h1>
      <p className="muted">
        Es la primera vez que se abre. Elige la contraseña de cada usuario: cada uno verá solo sus
        datos.
      </p>

      <form onSubmit={handleSubmit} className="login-body" noValidate>
        <UserPasswords
          id="gerard"
          name="Gerard"
          subtitle="Administrador"
          color="#0E6B58"
          type={type}
          value={values.gerard}
          repeat={values.gerardRepeat}
          onChange={(v) => update('gerard', v)}
          onRepeatChange={(v) => update('gerardRepeat', v)}
        />
        <UserPasswords
          id="padres"
          name="Padres"
          subtitle="Cuenta compartida"
          color="#3555A0"
          type={type}
          value={values.padres}
          repeat={values.padresRepeat}
          onChange={(v) => update('padres', v)}
          onRepeatChange={(v) => update('padresRepeat', v)}
        />

        <label className="check">
          <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
          Mostrar las contraseñas
        </label>

        {error && (
          <span className="err" role="alert">
            {error}
          </span>
        )}

        <button type="submit" className="btn btn-primary" disabled={sending}>
          {sending ? 'Creando usuarios…' : 'Crear usuarios'}
        </button>
      </form>
    </Screen>
  );
}

type UserPasswordsProps = {
  id: string;
  name: string;
  subtitle: string;
  color: string;
  type: 'text' | 'password';
  value: string;
  repeat: string;
  onChange: (value: string) => void;
  onRepeatChange: (value: string) => void;
};

function UserPasswords(props: UserPasswordsProps) {
  const { id, name, subtitle, color, type, value, repeat, onChange, onRepeatChange } = props;
  return (
    <fieldset className="user-block" style={{ margin: 0 }}>
      <legend className="sr-only">Contraseña de {name}</legend>
      <div className="row">
        <span className="avatar" style={{ background: color }} aria-hidden="true">
          {name[0]}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <strong style={{ fontSize: 17 }}>{name}</strong>
          <span className="muted" style={{ fontSize: 13 }}>
            {subtitle}
          </span>
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${id}-pwd`}>Contraseña (mínimo {MIN_LENGTH} caracteres)</label>
        <input
          id={`${id}-pwd`}
          type={type}
          autoComplete="new-password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-repeat`}>Repite la contraseña</label>
        <input
          id={`${id}-repeat`}
          type={type}
          autoComplete="new-password"
          value={repeat}
          onChange={(e) => onRepeatChange(e.target.value)}
        />
      </div>
    </fieldset>
  );
}
