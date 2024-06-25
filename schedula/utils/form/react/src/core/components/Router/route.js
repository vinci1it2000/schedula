import {Route} from 'react-router-dom';

export default function Component({children, render, ...props}) {
    return <Route {...props}>{children}</Route>;
}