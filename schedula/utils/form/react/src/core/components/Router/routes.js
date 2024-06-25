import {Routes} from 'react-router-dom';

export default function Component({children, render, ...props}) {
    return <Routes {...props}>{children}</Routes>;
}