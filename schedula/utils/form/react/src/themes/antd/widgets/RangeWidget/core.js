import React, {useEffect, useState} from "react";
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

    const [editedValue, setEditedValue] = useState(undefined)
    const [timeoutId, setTimeoutId] = useState(undefined)

    const handleChange = (nextValue) => {
        setEditedValue(nextValue === "" ? emptyValue : nextValue);
    }

    const _onChange = () => {
        if (editedValue !== undefined)
            onChange(editedValue)
    };
    useEffect(() => {
        if (timeoutId !== undefined)
            clearTimeout(timeoutId)
        setTimeoutId(setTimeout(() => {
            _onChange()
        }, 1000));

    }, [editedValue])
    const handleBlur = ({target: value}) => {
        _onChange();
        setEditedValue(undefined)
        onBlur(id, value)
    };
    const handleChangeComplete = (nextValue) => {
        onChange(nextValue)
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

    return (
        <Slider
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
    );
}