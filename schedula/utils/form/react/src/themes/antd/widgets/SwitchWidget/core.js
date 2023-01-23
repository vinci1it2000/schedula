import React from "react";
import {Switch} from "antd";
import {CheckOutlined, CloseOutlined} from '@ant-design/icons';
import {ariaDescribedByIds} from "@rjsf/utils";

export default function SwitchWidget(props) {
    const {
        autofocus,
        disabled,
        formContext,
        id,
        label,
        onBlur,
        onChange,
        onFocus,
        options,
        readonly,
        value,
    } = props;
    const {readonlyAsDisabled = true} = formContext;

    const handleChange = (checked) =>
        onChange(checked);

    const handleBlur = ({checked}) =>
        onBlur(id, checked);

    const handleFocus = ({checked}) =>
        onFocus(id, checked);

    const extraProps = {
        onBlur: !readonly ? handleBlur : undefined,
        onFocus: !readonly ? handleFocus : undefined,
    };

    return (
        <Switch
            checkedChildren={<CheckOutlined/>}
            unCheckedChildren={<CloseOutlined/>}
            autoFocus={autofocus}
            checked={typeof value === "undefined" ? false : value}
            disabled={disabled || (readonlyAsDisabled && readonly)}
            id={id}
            name={id}
            onChange={!readonly ? handleChange : undefined}
            {...extraProps}
            aria-describedby={ariaDescribedByIds(id)}>
            {options.onlyChildren ? null : (options.hasOwnProperty('label') ? options.label : label)}
        </Switch>
    );
}