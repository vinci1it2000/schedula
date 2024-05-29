import React, {useMemo, useState} from "react";
import {Slider} from "antd";
import {
    ariaDescribedByIds,
    rangeSpec
} from "@rjsf/utils";
import debounce from "lodash/debounce";


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

    const [editedValue, setEditedValue] = useState(undefined)

    const handleChange = (nextValue) => {
        setEditedValue(nextValue === "" ? emptyValue : nextValue);
        _update(nextValue)
    }

    const _clean = useMemo(() => (debounce(() => {
        setEditedValue(undefined)
    }, 1000)), [setEditedValue]);
    const _update = useMemo(() => (debounce((nextValue) => {
        onChange(nextValue)
    }, 500)), [onChange]);

    const handleBlur = ({target: value}) => {
        onBlur(id, value)
        _clean()
    };
    const handleChangeComplete = (nextValue) => {
        onChange(nextValue)
        _clean()
    }
    const handleFocus = ({target: value}) => {
        onFocus(id, value)
    };

    const extraProps = {
        placeholder,
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
        ...options
    };

    return <Slider
        autoFocus={autofocus}
        disabled={disabled || (readonlyAsDisabled && readonly)}
        id={id}
        max={max}
        min={min}
        onChangeComplete={!readonly ? handleChangeComplete : undefined}
        onChange={!readonly ? handleChange : undefined}
        range={range}
        step={step}
        value={editedValue === undefined ? value : editedValue}
        {...extraProps}
        aria-describedby={ariaDescribedByIds(id)}
    />
}