import React from 'react';

interface UserCardProps {
  name: string;
  email: string;
  avatarUrl?: string;
}

/**
 * UserCard component displays user profile information
 * in a compact card format.
 */
export const UserCard: React.FC<UserCardProps> = ({
  name,
  email,
  avatarUrl
}) => {
  return (
    <article
      className="user-card"
      aria-label="User profile card"
      style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        padding: '16px',
        gap: '12px',
        backgroundColor: '#ffffff',
        border: '1px solid #e0e0e0',
        borderRadius: '8px',
      }}
    >
      <img
        src={avatarUrl || '/default-avatar.png'}
        alt={`${name}'s avatar`}
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          objectFit: 'cover',
        }}
      />
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <span
          style={{
            fontSize: '18px',
            fontWeight: 600,
            color: '#1a1a1a',
          }}
        >
          {name}
        </span>
        <span
          style={{
            fontSize: '14px',
            fontWeight: 400,
            color: '#666666',
          }}
        >
          {email}
        </span>
      </div>
    </article>
  );
};

export default UserCard;
