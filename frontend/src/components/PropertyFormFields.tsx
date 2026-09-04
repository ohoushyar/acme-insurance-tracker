export function PropertyFormFields({
  label,
  address,
  statedValue,
  onLabelChange,
  onAddressChange,
  onStatedValueChange,
}: {
  label: string;
  address: string;
  statedValue: string;
  onLabelChange: (value: string) => void;
  onAddressChange: (value: string) => void;
  onStatedValueChange: (value: string) => void;
}) {
  return (
    <>
      <div className="review-field">
        <label htmlFor="property-label">Label</label>
        <input
          id="property-label"
          name="label"
          type="text"
          value={label}
          onChange={(event) => onLabelChange(event.target.value)}
          required
        />
      </div>
      <div className="review-field">
        <label htmlFor="property-address">Address</label>
        <input
          id="property-address"
          name="address"
          type="text"
          value={address}
          onChange={(event) => onAddressChange(event.target.value)}
        />
      </div>
      <div className="review-field">
        <label htmlFor="property-stated-value">Stated value</label>
        <input
          id="property-stated-value"
          name="stated_value"
          type="text"
          value={statedValue}
          onChange={(event) => onStatedValueChange(event.target.value)}
        />
      </div>
    </>
  );
}
