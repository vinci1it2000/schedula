import {BrowserRouter} from 'react-router-dom';

export default function Component({children, render, ...props}) {
    return <BrowserRouter {...props}>{children}</BrowserRouter>;
}