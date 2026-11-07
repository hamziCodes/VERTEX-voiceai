import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";

type FieldControlProps = {
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  id?: string;
  name?: string;
};

export function FormField({
  children,
  error,
  hint,
  label,
  name,
}: {
  children: ReactElement<FieldControlProps>;
  error?: string;
  hint?: string;
  label: ReactNode;
  name: string;
}) {
  const descriptionId = hint || error ? `${name}-description` : undefined;
  const control = isValidElement(children)
    ? cloneElement(children, {
        "aria-describedby": descriptionId,
        "aria-invalid": Boolean(error) || undefined,
        id: children.props.id ?? name,
        name: children.props.name ?? name,
      })
    : children;

  return (
    <div className="form-field">
      <label htmlFor={children.props.id ?? name}>{label}</label>
      {control}
      {descriptionId ? (
        <div className="form-field__description" id={descriptionId}>
          {hint ? <p className="form-field__hint">{hint}</p> : null}
          {error ? <p className="form-field__error">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
