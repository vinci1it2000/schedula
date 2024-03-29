import React from "react";

export default function Element({children, render, type, ...props}) {
    return React.createElement(type, props, children)
}