import {Link} from 'react-router-dom';

export default function Component({children, render, ...props}) {
    return <Link {...props}>{children}</Link>;
}