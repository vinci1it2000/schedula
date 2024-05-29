import React from "react";
import {Rate} from "antd";
import {
    ariaDescribedByIds,
    rangeSpec
} from "@rjsf/utils";


export default function RateWidget(props) {
    const {
        autofocus,
        disabled,
        formContext,
        id,
        onBlur,
        onChange,
        onFocus,
        options,
        readonly,
        schema,
        value,
    } = props;
    const {readonlyAsDisabled = true} = formContext;
    const count = options.count || 5;
    const {min = 0, max = 100} = rangeSpec(schema);

    const emptyValue = options.emptyValue || "";

    const handleChange = (nextValue) =>
        onChange((nextValue === "" ? emptyValue : nextValue) * (max - min) / count + min);

    const handleBlur = () => onBlur(id, value);

    const handleFocus = () => onFocus(id, value);

    const extraProps = {
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
        ...options
    };

    return (
        <Rate
            autoFocus={autofocus}
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            count={count}
            onChange={!readonly ? handleChange : undefined}
            range={false}
            value={(value - min) / (max - min) * count}
            {...extraProps}
            aria-describedby={ariaDescribedByIds(id)}
        />
    );
}