import React from "react";
import Slider from "antd/lib/slider";
import {
    ariaDescribedByIds,
    rangeSpec
} from "@rjsf/utils";


export default function RangeWidget(props) {
    const {
        autofocus,
        disabled,
        formContext,
        id,
        onBlur,
        onChange,
        onFocus,
        options,
        placeholder,
        readonly,
        schema,
        value,
    } = props;
    const {readonlyAsDisabled = true} = formContext;
    const range = schema.type === 'array'
    const {min, max, step} = rangeSpec(range ? schema.items : schema);
    const emptyValue = options.emptyValue || "";
    const handleChange = (nextValue) =>
        onChange(nextValue === "" ? emptyValue : nextValue);
    const handleBlur = () => onBlur(id, value);
    const handleFocus = () => onFocus(id, value);

    const extraProps = {
        placeholder,
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
        ...options
    };

    return (
        <Slider
            autoFocus={autofocus}
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            max={max}
            min={min}
            onChange={!readonly ? handleChange : undefined}
            range={range}
            step={step}
            value={value}
            {...extraProps}
            aria-describedby={ariaDescribedByIds(id)}
        />
    );
}